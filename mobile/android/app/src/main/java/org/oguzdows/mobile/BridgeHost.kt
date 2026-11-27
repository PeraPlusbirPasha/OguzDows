package org.oguzdows.mobile

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest

class BridgeDenied(val status: Int = 403) : Exception("OğuzKöprü isteği reddedildi ($status)")
data class BridgeItem(val id:String,val name:String,val bytes:Long,val sha256:String,var status:String="ready",val peer:String="") {
    fun json()=JSONObject().put("id",id).put("name",name).put("bytes",bytes).put("sha256",sha256)
}
data class BridgePeer(val id:String,val name:String,val code:String)
data class BridgePair(val id:String,val name:String,val nonce:String,val code:String,var status:String="pending",val until:Long)
data class BridgeReply(val status:Int=200,val mime:String="application/json",val bytes:ByteArray=ByteArray(0),val file:File?=null)

/** Memory-only peers/tokens. A short-lived session exposes only explicitly staged private copies. */
class BridgeHost(context:Context, val name:String) : AutoCloseable {
    val root=File(context.cacheDir,"kopru-${BridgeRules.token(16)}").apply{check(mkdirs())}
    val started=SystemClock.elapsedRealtime()
    private val guard=Any()
    @Volatile var closed=false; private set
    var secret=BridgeRules.token(); private set
    private var inviteUntil=started+120000
    private val attempts=ArrayDeque<Long>()
    private val pairs=linkedMapOf<String,BridgePair>()
    private val peers=linkedMapOf<String,BridgePeer>()
    private val files=linkedMapOf<String,BridgeItem>()
    private val inbox=linkedMapOf<String,BridgeItem>()
    @Volatile var frame:ByteArray=ByteArray(0);private set
    private var frameAt=0L
    @Volatile var viewer:String?=null;private set
    val server=BridgeServer(context,this)
    fun start():BridgeHost {try {server.start();return this} catch(error:Exception){close();throw error}}
    fun live(){if(closed || SystemClock.elapsedRealtime()-started>BridgeRules.TTL)throw BridgeDenied(410)}
    fun snapshot():Triple<List<BridgePair>,List<BridgePeer>,List<BridgeItem>> = synchronized(guard) {
        Triple(pairs.values.map{it.copy()},peers.values.toList(),inbox.values.map{it.copy()})
    }
    fun offered():List<BridgeItem> = synchronized(guard){files.values.filter{it.status=="ready"}.map{it.copy()}}
    fun renew()=synchronized(guard){live();secret=BridgeRules.token();inviteUntil=SystemClock.elapsedRealtime()+120000;pairs.clear()}
    fun approvePair(id:String,allow:Boolean)=synchronized(guard){live();val p=pairs[id]?:throw BridgeDenied();if(p.status!="pending"||p.until<SystemClock.elapsedRealtime())throw BridgeDenied();p.status=if(allow)"approved" else "rejected"}
    fun approveInbox(id:String,allow:Boolean)=synchronized(guard){live();val f=inbox[id]?:throw BridgeDenied();if(f.status!="pending")throw BridgeDenied();f.status=if(allow)"approved" else "rejected"}
    fun revoke(id:String)=synchronized(guard){peers.remove(id);if(viewer==id)stopMirror();inbox.values.filter{it.peer==id}.map{it.id}.forEach{inbox.remove(it);File(root,it).delete()};Unit}
    fun permitMirror(peer:String)=synchronized(guard){live();require(peers.containsKey(peer));viewer=peer;frame=ByteArray(0)}
    fun stopMirror(){viewer=null;frame=ByteArray(0);frameAt=0L}
    fun frame(bytes:ByteArray){live();if(viewer!=null && bytes.size<=BridgeRules.MAX_FRAME && bytes.size>=3 && bytes[0]==0xff.toByte() && bytes[1]==0xd8.toByte()){frame=bytes;frameAt=SystemClock.elapsedRealtime()}}
    fun received(id:String):Pair<BridgeItem,File> = synchronized(guard){live();val f=inbox[id]?:throw BridgeDenied(404);check(f.status=="ready");f.copy() to File(root,id)}
    private fun reserve(bytes:Long){
        if(files.size+inbox.size>=BridgeRules.MAX_ITEMS || (files.values.sumOf{it.bytes}+inbox.values.sumOf{it.bytes}+bytes)>BridgeRules.BUDGET)throw BridgeDenied(413)
        if(root.usableSpace<bytes+16*1024*1024)throw BridgeDenied(507)
    }
    fun offer(input:InputStream,label:String):BridgeItem {
        BridgeRules.name(label);val id=BridgeRules.token(16);val target=File(root,id)
        synchronized(guard){live();reserve(BridgeRules.MAX_FILE);files[id]=BridgeItem(id,label,BridgeRules.MAX_FILE,"", "staging")}
        try {
            val(size,hash)=target.outputStream().use{output->input.use{BridgeRules.copy(it,output,BridgeRules.MAX_FILE)}}
            return synchronized(guard){live();val item=BridgeItem(id,label,size,hash);files[id]=item;item.copy()}
        }catch(error:Exception){synchronized(guard){files.remove(id)};target.delete();throw error}
    }
    private fun auth(header:String):String {
        live();if(!header.startsWith("Bearer "))throw BridgeDenied(401)
        val hash=BridgeRules.sha(header.substring(7).toByteArray(Charsets.UTF_8))
        if(!peers.containsKey(hash))throw BridgeDenied(401)
        return hash
    }
    fun ensureAuthorized(header:String) { synchronized(guard) { auth(header) } }
    private fun json(value:JSONObject,status:Int=200)=BridgeReply(status,bytes=value.toString().toByteArray(Charsets.UTF_8))
    fun route(method:String,path:String,headers:Map<String,String>,input:InputStream):BridgeReply {
        val length=headers["content-length"]?.toLongOrNull()?:0L
        fun body():JSONObject {
            if(length !in 0..8192)throw BridgeDenied(413)
            val data=ByteArray(length.toInt());var at=0
            while(at<data.size){val n=input.read(data,at,data.size-at);if(n<=0)throw BridgeDenied(400);at+=n}
            return JSONObject(data.toString(Charsets.UTF_8))
        }
        synchronized(guard){live()}
        if(method=="POST" && path=="/v1/pair") {
            val b=body()
            return synchronized(guard){
                live();val now=SystemClock.elapsedRealtime();while(attempts.isNotEmpty() && now-attempts.first()>60000)attempts.removeFirst()
                if(attempts.size>=6)throw BridgeDenied(429);attempts.addLast(now)
                if(now>inviteUntil || !MessageDigest.isEqual(b.optString("secret").toByteArray(),secret.toByteArray()))throw BridgeDenied()
                if(pairs.size+peers.size>=2)throw BridgeDenied(429)
                val peerName=BridgeRules.name(b.getString("name")).take(80);val nonce=b.getString("nonce");require(BridgeRules.hash(nonce))
                val id=BridgeRules.token(16);val code=BridgeRules.sha((id+nonce).toByteArray()).take(8).uppercase(java.util.Locale.ROOT)
                pairs[id]=BridgePair(id,peerName,nonce,code,until=now+120000)
                json(JSONObject().put("id",id).put("code",code).put("status","pending"))
            }
        }
        if(method=="POST" && path=="/v1/pair/status") {
            val b=body()
            return synchronized(guard){live();val p=pairs[b.optString("id")]?:throw BridgeDenied()
                if(SystemClock.elapsedRealtime()>p.until || !MessageDigest.isEqual(p.nonce.toByteArray(),b.optString("nonce").toByteArray()))throw BridgeDenied()
                if(p.status=="approved") {
                    val token=BridgeRules.token();val key=BridgeRules.sha(token.toByteArray());peers[key]=BridgePeer(key,p.name,p.code);pairs.remove(p.id)
                    json(JSONObject().put("status","approved").put("token",token).put("name",name))
                }else json(JSONObject().put("status",p.status))
            }
        }
        val peer=synchronized(guard){auth(headers["authorization"]?:"")}
        synchronized(guard){
            auth(headers["authorization"]?:"")
            if(method=="GET" && path=="/v1/state")return json(JSONObject().put("version",1).put("name",name).put("files",JSONArray().apply{files.values.filter{it.status=="ready"}.forEach{put(it.json())}}).put("mirror",viewer==peer))
            if(method=="POST" && path=="/v1/bye"){revoke(peer);return json(JSONObject().put("stopped",true))}
            if(method=="GET" && path=="/v1/frame") {
                if(viewer!=peer)throw BridgeDenied()
                return if(frame.isNotEmpty() && SystemClock.elapsedRealtime()-frameAt<3000)BridgeReply(200,"image/jpeg",frame)else BridgeReply(204,"image/jpeg")
            }
            if(method=="GET" && path.startsWith("/v1/files/")){
                val id=path.removePrefix("/v1/files/");if(!BridgeRules.id(id))throw BridgeDenied(404)
                val f=files[id]?.takeIf{it.status=="ready"}?:throw BridgeDenied(404)
                return BridgeReply(200,"application/octet-stream",file=File(root,f.id))
            }
        }
        if(method=="POST" && path=="/v1/inbox") {
            val b=body();val label=BridgeRules.name(b.getString("name"));val size=b.getLong("bytes");val hash=b.getString("sha256")
            require(size in 0..BridgeRules.MAX_FILE && BridgeRules.hash(hash))
            return synchronized(guard){auth(headers["authorization"]?:"");reserve(size);val id=BridgeRules.token(16);inbox[id]=BridgeItem(id,label,size,hash,"pending",peer);json(JSONObject().put("id",id).put("status","pending"),201)}
        }
        if(path.startsWith("/v1/inbox/")) {
            val id=path.removePrefix("/v1/inbox/");if(!BridgeRules.id(id))throw BridgeDenied(404)
            val item=synchronized(guard){auth(headers["authorization"]?:"");val f=inbox[id]?.takeIf{it.peer==peer}?:throw BridgeDenied(404)
                if(method=="GET")return json(JSONObject().put("id",id).put("status",f.status))
                if(method!="PUT" || f.status!="approved" || length!=f.bytes)throw BridgeDenied()
                f.status="receiving";f
            }
            val target=File(root,id)
            try {
                target.outputStream().use{out->var remaining=length;val buffer=ByteArray(65536)
                    while(remaining>0){synchronized(guard){auth(headers["authorization"]?:"")};val n=input.read(buffer,0,minOf(buffer.size.toLong(),remaining).toInt());if(n<=0)throw BridgeDenied(400);out.write(buffer,0,n);remaining-=n}
                }
                BridgeRules.verify(target,item.bytes,item.sha256)
                synchronized(guard){auth(headers["authorization"]?:"");item.status="ready"}
                return json(JSONObject().put("id",id).put("status","ready"),201)
            } catch(error:Exception){target.delete();synchronized(guard){item.status="failed"};throw error}
        }
        throw BridgeDenied(404)
    }
    override fun close(){if(closed)return;closed=true;stopMirror();server.close();synchronized(guard){pairs.clear();peers.clear();files.clear();inbox.clear()};root.deleteRecursively()}
}
