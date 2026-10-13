// Briefly flash a border around the split that just gained focus, fading out.
// Accent is ANSI blue from the active theme.
const float DURATION = 0.35;  // seconds
const float BORDER = 6.0;     // border width in device pixels

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec4 color = texture(iChannel0, uv);

    float t = iTime - iTimeFocus;
    if (iFocus > 0 && t < DURATION) {
        vec2 edge = min(fragCoord, iResolution.xy - fragCoord);
        if (min(edge.x, edge.y) < BORDER) {
            float fade = 1.0 - smoothstep(0.0, DURATION, t);
            color.rgb = mix(color.rgb, iPalette[4], fade);
        }
    }

    fragColor = color;
}
