package org.oguzdows.mobile

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Glass is bounded tint/light, not a live full-screen blur shader. */
@Composable
fun GlassSurface(modifier: Modifier = Modifier, dark: Boolean = LocalAero.current.dark, light: Boolean = LocalAero.current.light,
                 content: @Composable BoxScope.() -> Unit) {
    val shape = RoundedCornerShape(18.dp)
    val glass = LocalAero.current.glass && !light
    val colors = if (dark) listOf(Color(0xFF2A3C43).copy(alpha=if(glass).72f else 1f), Color(0xFF1B2A31).copy(alpha=if(glass).84f else 1f))
                 else listOf(Color.White.copy(alpha = if(glass) .70f else .98f), Color(0xFFE7EEEA).copy(alpha=if(glass).84f else 1f))
    Box(modifier.clip(shape).background(Brush.linearGradient(colors))
        .border(1.dp, if (dark) Color.White.copy(.14f) else Color.White.copy(.72f), shape), content = content)
}

@Composable
fun ShellGlyph(name: String, modifier: Modifier = Modifier, tint: Color = Color(0xFF294C46)) {
    Canvas(modifier.size(24.dp)) {
        val scale = size.minDimension / 24f
        withTransform({ scale(scale, scale, Offset.Zero) }) {
            val stroke = Stroke(1.65f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            fun line(x: Float, y: Float, x2: Float, y2: Float) = drawLine(tint, Offset(x,y), Offset(x2,y2), 1.65f, StrokeCap.Round)
            fun circle(x: Float, y: Float, radius: Float) = drawCircle(tint, radius, Offset(x,y), style = stroke)
            fun rect(x: Float, y: Float, w: Float, h: Float) = drawRoundRect(tint, Offset(x,y), Size(w,h), CornerRadius(2f), style = stroke)
            when (name) {
                "phone" -> drawPath(Path().apply { moveTo(6f,3f); lineTo(3f,5f); cubicTo(3f,13f,11f,21f,19f,21f); lineTo(21f,18f); lineTo(16f,14f); lineTo(13f,16f); lineTo(8f,11f); lineTo(10f,8f); close() }, tint, style = stroke)
                "message" -> { rect(3f,4f,18f,13f); line(8f,17f,5f,21f); line(5f,21f,5f,17f); line(7f,9f,17f,9f); line(7f,12f,14f,12f) }
                "contacts" -> { rect(5f,3f,15f,18f); circle(12.5f,9f,2.5f); drawArc(tint,180f,180f,false,Offset(8f,14f),Size(9f,7f),style=stroke); line(3f,7f,6f,7f); line(3f,12f,6f,12f) }
                "store" -> { rect(4f,7f,16f,14f); drawArc(tint,180f,180f,false,Offset(8f,2f),Size(8f,10f),style=stroke) }
                "globe" -> { circle(12f,12f,9f); drawOval(tint,Offset(8f,3f),Size(8f,18f),style=stroke); line(3f,12f,21f,12f); line(5f,7f,19f,7f); line(5f,17f,19f,17f) }
                "music" -> { line(10f,17f,10f,5f); line(10f,5f,20f,3f); line(20f,3f,20f,15f); drawOval(tint,Offset(4f,16f),Size(6f,4f)); drawOval(tint,Offset(14f,14f),Size(6f,4f)) }
                "image" -> { rect(3f,4f,18f,16f); circle(16.5f,8.5f,1.5f); drawPath(Path().apply {moveTo(4f,18f);lineTo(9f,11f);lineTo(14f,17f);lineTo(17f,14f);lineTo(20f,18f)},tint,style=stroke) }
                "settings", "controls" -> { line(5f,3f,5f,21f); line(12f,3f,12f,21f); line(19f,3f,19f,21f); drawCircle(Color(0xFFE8EFEA),3f,Offset(5f,8f)); circle(5f,8f,2.5f); drawCircle(Color(0xFFE8EFEA),3f,Offset(12f,16f)); circle(12f,16f,2.5f); drawCircle(Color(0xFFE8EFEA),3f,Offset(19f,9f)); circle(19f,9f,2.5f) }
                "search" -> { circle(10.5f,10.5f,6.5f); line(15.5f,15.5f,21f,21f) }
                "apps" -> for (x in listOf(5f,12f,19f)) for (y in listOf(5f,12f,19f)) drawCircle(tint,1.6f,Offset(x,y))
                "clock" -> { circle(12f,12f,9f); line(12f,6f,12f,12f); line(12f,12f,16f,14f) }
                "calendar" -> { rect(3f,5f,18f,16f); line(7f,3f,7f,8f);line(17f,3f,17f,8f);line(3f,11f,21f,11f);line(8f,15f,10f,15f);line(14f,15f,16f,15f) }
                "notes", "news", "tasks" -> { rect(5f,3f,15f,18f);for(y in listOf(8f,12f,16f)) line(9f,y,16f,y); if(name=="tasks") {line(3f,8f,5f,10f);line(5f,10f,8f,6f)} }
                "folder" -> drawPath(Path().apply {moveTo(3f,6f);lineTo(10f,6f);lineTo(12f,9f);lineTo(21f,9f);lineTo(21f,20f);lineTo(3f,20f);close()},tint,style=stroke)
                "calculator" -> { rect(5f,2f,14f,20f);rect(8f,5f,8f,4f);for(x in listOf(9f,15f))for(y in listOf(13f,17f)) drawCircle(tint,1f,Offset(x,y)) }
                "monitor" -> { rect(3f,3f,18f,14f);line(12f,17f,12f,21f);line(7f,21f,17f,21f);line(6f,12f,9f,8f);line(9f,8f,12f,12f);line(12f,12f,17f,7f) }
                "tools" -> { circle(8f,8f,4f);rect(13f,13f,8f,8f);drawPath(Path().apply {moveTo(3f,21f);lineTo(8f,13f);lineTo(12f,21f);close()},tint,style=stroke) }
                "plus" -> {line(12f,5f,12f,19f);line(5f,12f,19f,12f)}
                "close" -> {line(6f,6f,18f,18f);line(18f,6f,6f,18f)}
                else -> {circle(12f,12f,8f);line(8f,12f,16f,12f)}
            }
        }
    }
}

@Composable
fun DestinationIcon(destination: ShellDestination, size: Int = 52) {
    if (destination.id == "rifki") Image(painterResource(R.drawable.rifki), null, Modifier.size(size.dp))
    else Box(Modifier.size(size.dp).clip(RoundedCornerShape(16.dp))
        .background(Brush.linearGradient(listOf(Color.White.copy(.94f), Color(destination.color))))
        .border(1.dp, Color.White.copy(.7f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) {
        ShellGlyph(destination.glyph, Modifier.size((size * .5f).dp))
    }
}

@Composable
fun InstalledIcon(entry: LauncherEntry, repository: LauncherRepository, size: Int = 48) {
    var bitmap by remember(entry.key, entry.info) { mutableStateOf<android.graphics.Bitmap?>(null) }
    LaunchedEffect(entry.key, entry.info) {
        bitmap = withContext(Dispatchers.IO) { repository.icon(entry) }
    }
    if (bitmap != null) Image(bitmap!!.asImageBitmap(), null, Modifier.size(size.dp))
    else Box(Modifier.size(size.dp).clip(RoundedCornerShape(14.dp)).background(Color(0xFFDDE9E3)), contentAlignment = Alignment.Center) {
        Text(entry.label.take(1), fontSize = 22.sp, color = Color(0xFF244D43), fontWeight = FontWeight.Bold)
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun HomeShortcut(key: String, state: LauncherUiState, repository: LauncherRepository,
                 onOpen: (String) -> Unit, edit: (String) -> Unit, modifier: Modifier = Modifier) {
    val destination = LauncherRules.internalRoute(key)?.let { id -> LauncherRules.destinations.find { it.id == id } }
    val entry = state.entries.find { it.key == key }
    val label = destination?.label ?: entry?.label ?: if (state.loading) "Yükleniyor" else "Kullanılamıyor"
    val layout = ShellStyles.layout(state.layout)
    val tileModifier = if(layout.tiles) modifier.padding(4.dp).background(Color(ShellStyles.accent(state.wallpaper, false)).copy(alpha=.68f), RoundedCornerShape(12.dp)) else modifier
    Column(tileModifier.clip(RoundedCornerShape(14.dp)).combinedClickable(onClick = { onOpen(key) }, onLongClick = { edit(key) })
        .padding(vertical = 8.dp).semantics { contentDescription = "Kısayol: $label" }, horizontalAlignment = Alignment.CenterHorizontally) {
        when { destination != null -> DestinationIcon(destination)
            entry != null -> InstalledIcon(entry, repository, 52)
            else -> Box(Modifier.size(52.dp).background(Color.White.copy(.2f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) { ShellGlyph("apps", tint=Color.White) }
        }
        Spacer(Modifier.height(7.dp))
        Text(label, color = Color.White, fontSize = 12.sp, lineHeight = 15.sp, maxLines = 2,
            textAlign = TextAlign.Center, overflow = TextOverflow.Ellipsis,
            modifier = Modifier.fillMaxWidth().padding(horizontal=2.dp), style = MaterialTheme.typography.labelMedium)
    }
}
