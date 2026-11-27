package org.oguzdows.mobile

import android.Manifest
import android.content.ContentProviderOperation
import android.content.ContentUris
import android.content.Context
import android.provider.ContactsContract
import org.json.JSONArray
import org.json.JSONObject

/** System provider is the single source of truth. No address book copy/cloud sync or deletion. */
data class SystemContact(val id: Long, val name: String, val number: String)
object SystemContacts {
    const val LIMIT = 1000
    fun read(context: Context): List<SystemContact> {
        check(PlatformState.granted(context, Manifest.permission.READ_CONTACTS)) { "Rehber okuma izni kapalı." }
        val phone = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
        val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME_PRIMARY, ContactsContract.CommonDataKinds.Phone.NUMBER)
        val out = ArrayList<SystemContact>()
        context.contentResolver.query(phone, projection, null, null,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME_PRIMARY + " COLLATE LOCALIZED ASC")?.use { cursor ->
            var scanned = 0
            while (scanned < LIMIT && cursor.moveToNext()) {
                scanned++ // Invalid / duplicate numbers must not turn the 1000-row budget into an unbounded scan.
                val number = PlatformRules.number(cursor.getString(2) ?: "")
                if (number.isNotEmpty()) out.add(SystemContact(cursor.getLong(0), (cursor.getString(1) ?: number).take(120), number))
            }
        } ?: error("Sistem rehber sağlayıcısı yok.")
        return out.distinctBy { "${it.id}:${it.number}" }
    }
    @JvmStatic fun json(context: Context): JSONArray = JSONArray().apply {
        read(context).forEach { put(JSONObject().put("id", it.id.toString()).put("name", it.name).put("number", it.number)) }
    }
    /** Called ONLY after explicit native preview/confirmation. New local raw contact; never overwrite existing. */
    fun insert(context: Context, name: String, rawNumber: String): Long {
        check(PlatformState.granted(context, Manifest.permission.WRITE_CONTACTS)) { "Rehbere yazma izni kapalı." }
        val number = PlatformRules.number(rawNumber)
        require(name.isNotBlank() && name.length <= 120 && name.none(Char::isISOControl) && number.isNotEmpty())
        val raw = ContactsContract.RawContacts.CONTENT_URI
        val data = ContactsContract.Data.CONTENT_URI
        val operations = arrayListOf(
            ContentProviderOperation.newInsert(raw).withValue(ContactsContract.RawContacts.ACCOUNT_TYPE, null)
                .withValue(ContactsContract.RawContacts.ACCOUNT_NAME, null).build(),
            ContentProviderOperation.newInsert(data).withValueBackReference(ContactsContract.Data.RAW_CONTACT_ID, 0)
                .withValue(ContactsContract.Data.MIMETYPE, ContactsContract.CommonDataKinds.StructuredName.CONTENT_ITEM_TYPE)
                .withValue(ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME, name.trim()).build(),
            ContentProviderOperation.newInsert(data).withValueBackReference(ContactsContract.Data.RAW_CONTACT_ID, 0)
                .withValue(ContactsContract.Data.MIMETYPE, ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE)
                .withValue(ContactsContract.CommonDataKinds.Phone.NUMBER, number)
                .withValue(ContactsContract.CommonDataKinds.Phone.TYPE, ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE).build(),
        )
        val result = context.contentResolver.applyBatch(ContactsContract.AUTHORITY, operations)
        return ContentUris.parseId(requireNotNull(result.firstOrNull()?.uri))
    }
}
