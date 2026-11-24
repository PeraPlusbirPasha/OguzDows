#version 330
// Picom 12 GLX arayüzü. BACKDROP bulanıklığı bu shader'da taklit edilmez;
// dual_kawase kompozitör geçişindedir. Yalnız alfa dekorasyonun ışığını ekler.
in vec2 texcoord;
uniform sampler2D tex;
vec4 default_post_processing(vec4 color);

vec4 window_shader() {
    vec2 dimensions = vec2(textureSize(tex, 0));
    vec2 uv = texcoord / max(dimensions, vec2(1.0));
    vec4 color = texture(tex, uv);
    // Opak içerik, başlık yazısı ve pencere kontrol düğmeleri değişmez.
    float glass = step(0.01, color.a) * (1.0 - smoothstep(0.94, 0.999, color.a));
    float diagonal = uv.x * 0.65 + uv.y * 0.35;
    float streak = exp(-pow((diagonal - 0.30) * 28.0, 2.0));
    float echo = exp(-pow((diagonal - 0.54) * 43.0, 2.0));
    float rim = 1.0 - smoothstep(0.0, 1.5, min(texcoord.y, dimensions.y - texcoord.y));
    color.rgb += vec3(0.105 * streak + 0.04 * echo + 0.025 * rim) * color.a * glass;
    color.rgb = min(color.rgb, vec3(color.a)); // premultiplied alfa korunur.
    return default_post_processing(color);
}
