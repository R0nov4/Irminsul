import QtQuick
import ".."

// MoonPhase — a moon disc drawn from the REAL phase with the exact
// terminator formula, rotated by the topocentric bright-limb tilt so the
// crescent angle matches the real sky.
//
//   phase φ : 0 new · 0.25 first quarter · 0.5 full · 0.75 last quarter
//   c       = cos(2πφ)
//   lit area = (1 − c) / 2   → exactly the "% illuminated" shown in the UI
//
//   limb        (the lit half-circle) :  x = ±R · cos t
//   terminator  (the day/night line)  :  x = ±R · c · cos t     t ∈ [−π/2, π/2]
//
// The terminator is a half-ellipse with semi-axes (R·|c|, R): it is a
// straight line at the quarters (c = 0), bulges toward the dark side for a
// crescent and toward the lit side for a gibbous moon.
//
// The whole canvas is then rotated by `tilt` degrees so the bright limb
// points in the direction the observer actually sees.
//
// Visual enhancements:
//   · Earthshine: faint blue-grey glow on the unlit side (sunlight
//     reflected off the Earth onto the Moon's dark face)
//   · Maria: semi-transparent dark patches suggesting the lunar seas
//     (Mare Imbrium, Serenitatis, Tranquillitatis, etc.)
//   · Soft terminator: a 2-3 px penumbral gradient at the day/night
//     boundary instead of a hard edge
Item {
    id: root

    property real phase: 0.5
    property real tilt: 0             // bright-limb tilt in degrees (from data)
    // false → the icon is always drawn upright (lit side left/right only).
    // true  → rotate it by `tilt` like the real sky; that angle swings all
    //         day and is meaningless while the moon is below the horizon,
    //         which is how the crescent ended up lying on its back.
    property bool realSkyTilt: false
    property bool southern: false
    property color litColor: Theme.cream
    property bool showDark: true      // earthshine ghost of the unlit disc
    property real darkAlpha: 0.10
    property bool detailed: true      // maria + penumbra (disable for tiny sizes)

    onPhaseChanged: canvas.requestPaint()
    onTiltChanged: canvas.requestPaint()
    onRealSkyTiltChanged: canvas.requestPaint()
    onSouthernChanged: canvas.requestPaint()
    onLitColorChanged: canvas.requestPaint()
    onShowDarkChanged: canvas.requestPaint()
    onDetailedChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const R = Math.min(width, height) / 2 - 0.75
            if (R <= 0)
                return
            const cx = width / 2
            const cy = height / 2

            // ── apply tilt rotation (whole moon rotated) ────────────────
            const tiltRad = (root.realSkyTilt ? root.tilt : 0) * Math.PI / 180
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(tiltRad)
            ctx.translate(-cx, -cy)

            // ── earthshine: faint blue-tinted glow on unlit disc ────────
            if (root.showDark) {
                // outer earthshine disc (slightly blue-shifted)
                const esColor = Theme.alpha("#b8c4d8", root.darkAlpha * 0.7)
                ctx.fillStyle = esColor
                ctx.beginPath()
                ctx.arc(cx, cy, R, 0, Math.PI * 2)
                ctx.fill()
                // brighter rim
                ctx.strokeStyle = Theme.alpha("#b8c4d8", 0.18)
                ctx.lineWidth = 0.6
                ctx.stroke()
            }

            const phi = ((root.phase % 1) + 1) % 1
            const c = Math.cos(2 * Math.PI * phi)
            const illum = (1 - c) / 2

            // ── maria (lunar seas) — clipped to the full disc ──────────
            // drawn BEFORE the lit area so they show through both the
            // earthshine (very faintly) and the bright side (subtly)
            if (root.detailed && R >= 8) {
                ctx.save()
                ctx.beginPath()
                ctx.arc(cx, cy, R - 0.5, 0, Math.PI * 2)
                ctx.clip()
                _drawMaria(ctx, cx, cy, R)
                ctx.restore()
            }

            if (illum < 0.004) {
                // new moon: nothing lit, just the earthshine + maria
                ctx.restore()
                return
            }

            let sgn = phi <= 0.5 ? 1 : -1    // +1 → lit side on the right
            if (root.southern)
                sgn = -sgn

            const N = 72

            // ── soft terminator (penumbra) ─────────────────────────────
            // A narrow gradient strip along the terminator gives the
            // illusion of a gradual shadow transition.
            if (root.detailed && R >= 8) {
                const penW = Math.max(1.5, R * 0.08)  // penumbra width in px
                const penAlpha = 0.25
                for (let p = 0; p < 3; p++) {
                    const frac = (p + 1) / 4.0
                    const cShift = c + sgn * (penW / R) * (1 - frac)
                    ctx.fillStyle = Theme.alpha(root.litColor, penAlpha * frac)
                    ctx.beginPath()
                    for (let i = 0; i <= N; i++) {
                        const t = -Math.PI / 2 + Math.PI * i / N
                        const x = cx + sgn * cShift * R * Math.cos(t)
                        const y = cy + R * Math.sin(t)
                        if (i === 0) ctx.moveTo(x, y)
                        else ctx.lineTo(x, y)
                    }
                    for (let i = N; i >= 0; i--) {
                        const t = -Math.PI / 2 + Math.PI * i / N
                        ctx.lineTo(cx + sgn * c * R * Math.cos(t), cy + R * Math.sin(t))
                    }
                    ctx.closePath()
                    ctx.fill()
                }
            }

            // ── lit area ───────────────────────────────────────────────
            ctx.fillStyle = root.litColor
            ctx.beginPath()
            // lit limb: top → bottom along the lit side
            for (let i = 0; i <= N; i++) {
                const t = -Math.PI / 2 + Math.PI * i / N
                const x = cx + sgn * R * Math.cos(t)
                const y = cy + R * Math.sin(t)
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
            }
            // terminator: bottom → top (half-ellipse, semi-axis R·c)
            for (let i = N; i >= 0; i--) {
                const t = -Math.PI / 2 + Math.PI * i / N
                ctx.lineTo(cx + sgn * c * R * Math.cos(t), cy + R * Math.sin(t))
            }
            ctx.closePath()
            ctx.fill()

            // ── re-draw maria on the LIT side only (darker patches) ────
            if (root.detailed && R >= 8) {
                ctx.save()
                // clip to the lit crescent shape
                ctx.beginPath()
                for (let i = 0; i <= N; i++) {
                    const t = -Math.PI / 2 + Math.PI * i / N
                    const x = cx + sgn * R * Math.cos(t)
                    const y = cy + R * Math.sin(t)
                    if (i === 0) ctx.moveTo(x, y)
                    else ctx.lineTo(x, y)
                }
                for (let i = N; i >= 0; i--) {
                    const t = -Math.PI / 2 + Math.PI * i / N
                    ctx.lineTo(cx + sgn * c * R * Math.cos(t), cy + R * Math.sin(t))
                }
                ctx.closePath()
                ctx.clip()
                _drawMaria(ctx, cx, cy, R)
                ctx.restore()
            }

            ctx.restore()  // undo tilt rotation
        }

        // ── maria / crater features ────────────────────────────────────
        // Semi-transparent grey ellipses suggesting the major lunar seas.
        // Positions are in normalized coordinates (-1..+1) relative to
        // the disc center, mapped from a simple lunar-face reference.
        function _drawMaria(ctx, cx, cy, R) {
            const maria = [
                // [x, y, rx, ry, alpha]  — normalized to R
                // Mare Imbrium (upper-left quadrant)
                [-0.22, -0.30, 0.22, 0.18, 0.08],
                // Mare Serenitatis (upper-right of center)
                [ 0.12, -0.24, 0.14, 0.13, 0.07],
                // Mare Tranquillitatis (right of center)
                [ 0.22, -0.04, 0.16, 0.14, 0.07],
                // Mare Crisium (far right)
                [ 0.42,-0.16, 0.08, 0.06, 0.06],
                // Oceanus Procellarum (large, left side)
                [-0.36, -0.02, 0.18, 0.30, 0.06],
                // Mare Nubium (lower-left)
                [-0.14,  0.26, 0.14, 0.10, 0.06],
                // Mare Humorum (lower-far-left)
                [-0.32,  0.30, 0.08, 0.07, 0.05],
                // Mare Fecunditatis (lower-right)
                [ 0.28,  0.14, 0.12, 0.10, 0.06],
                // small crater shadows
                [-0.06, -0.48, 0.04, 0.04, 0.04],
                [ 0.34, -0.38, 0.03, 0.03, 0.04],
                [-0.10,  0.42, 0.05, 0.04, 0.04],
            ]

            for (let m = 0; m < maria.length; m++) {
                const mx = maria[m][0], my = maria[m][1]
                const mrx = maria[m][2], mry = maria[m][3]
                const ma = maria[m][4]

                ctx.fillStyle = Theme.alpha("#3a3a4a", ma)
                ctx.beginPath()
                ctx.ellipse(cx + mx * R, cy + my * R,
                            mrx * R, mry * R,
                            0, 0, Math.PI * 2)
                ctx.fill()
            }
        }
    }
}
