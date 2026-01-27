/**
 * Organic Blob Creature - follows cursor with smooth organic movements
 * Inspired by Google Antigravity aesthetic
 */

class OrganicCreature {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            this.canvas = document.createElement('canvas');
            this.canvas.id = canvasId;
            document.body.prepend(this.canvas);
        }

        this.ctx = this.canvas.getContext('2d');
        this.resize();

        // Mouse position
        this.mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
        this.targetMouse = { x: this.mouse.x, y: this.mouse.y };

        // Creature properties
        this.creature = {
            x: window.innerWidth / 2,
            y: window.innerHeight / 2,
            radius: 120,
            points: [],
            numPoints: 12,
            tension: 0.3,
            velocity: { x: 0, y: 0 }
        };

        // Initialize blob points
        this.initPoints();

        // Animation
        this.time = 0;
        this.running = true;

        // Colors - gradient from purple to blue to teal
        this.colors = {
            primary: 'rgba(138, 180, 248, 0.15)',      // soft blue
            secondary: 'rgba(197, 138, 249, 0.12)',    // soft purple
            tertiary: 'rgba(129, 201, 149, 0.10)',     // soft green
            glow: 'rgba(138, 180, 248, 0.05)'
        };

        // Bind events
        this.bindEvents();

        // Start animation
        this.animate();
    }

    initPoints() {
        this.creature.points = [];
        for (let i = 0; i < this.creature.numPoints; i++) {
            const angle = (i / this.creature.numPoints) * Math.PI * 2;
            this.creature.points.push({
                baseAngle: angle,
                angle: angle,
                radius: this.creature.radius,
                baseRadius: this.creature.radius,
                noiseOffset: Math.random() * 1000,
                velocity: 0
            });
        }
    }

    bindEvents() {
        window.addEventListener('resize', () => this.resize());

        document.addEventListener('mousemove', (e) => {
            this.targetMouse.x = e.clientX;
            this.targetMouse.y = e.clientY;
        });

        document.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                this.targetMouse.x = e.touches[0].clientX;
                this.targetMouse.y = e.touches[0].clientY;
            }
        });
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '0';
    }

    // Simplex noise approximation
    noise(x, y, z) {
        const X = Math.floor(x) & 255;
        const Y = Math.floor(y) & 255;
        const Z = Math.floor(z) & 255;

        x -= Math.floor(x);
        y -= Math.floor(y);
        z -= Math.floor(z);

        const u = this.fade(x);
        const v = this.fade(y);
        const w = this.fade(z);

        // Simple hash function
        const hash = (n) => {
            const x = Math.sin(n) * 43758.5453123;
            return x - Math.floor(x);
        };

        const a = hash(X + Y * 57 + Z * 113);
        const b = hash(X + 1 + Y * 57 + Z * 113);
        const c = hash(X + (Y + 1) * 57 + Z * 113);
        const d = hash(X + 1 + (Y + 1) * 57 + Z * 113);
        const e = hash(X + Y * 57 + (Z + 1) * 113);
        const f = hash(X + 1 + Y * 57 + (Z + 1) * 113);
        const g = hash(X + (Y + 1) * 57 + (Z + 1) * 113);
        const h = hash(X + 1 + (Y + 1) * 57 + (Z + 1) * 113);

        return this.lerp(w,
            this.lerp(v, this.lerp(u, a, b), this.lerp(u, c, d)),
            this.lerp(v, this.lerp(u, e, f), this.lerp(u, g, h))
        ) * 2 - 1;
    }

    fade(t) {
        return t * t * t * (t * (t * 6 - 15) + 10);
    }

    lerp(t, a, b) {
        return a + t * (b - a);
    }

    update() {
        this.time += 0.008;

        // Smooth mouse following
        this.mouse.x += (this.targetMouse.x - this.mouse.x) * 0.08;
        this.mouse.y += (this.targetMouse.y - this.mouse.y) * 0.08;

        // Calculate direction to mouse
        const dx = this.mouse.x - this.creature.x;
        const dy = this.mouse.y - this.creature.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Organic movement - slower, more lazy following
        const speed = Math.min(distance * 0.02, 8);
        if (distance > 1) {
            this.creature.velocity.x += (dx / distance) * speed * 0.1;
            this.creature.velocity.y += (dy / distance) * speed * 0.1;
        }

        // Apply velocity with damping
        this.creature.velocity.x *= 0.92;
        this.creature.velocity.y *= 0.92;

        this.creature.x += this.creature.velocity.x;
        this.creature.y += this.creature.velocity.y;

        // Update blob points with organic deformation
        const velocityMagnitude = Math.sqrt(
            this.creature.velocity.x ** 2 +
            this.creature.velocity.y ** 2
        );

        const velocityAngle = Math.atan2(
            this.creature.velocity.y,
            this.creature.velocity.x
        );

        this.creature.points.forEach((point, i) => {
            // Noise-based organic movement
            const noiseVal = this.noise(
                point.noiseOffset + this.time * 0.5,
                i * 0.3,
                this.time * 0.3
            );

            // Stretch in direction of movement
            const angleDiff = Math.abs(
                Math.atan2(
                    Math.sin(point.baseAngle - velocityAngle),
                    Math.cos(point.baseAngle - velocityAngle)
                )
            );

            const stretch = 1 + (velocityMagnitude * 0.02) * Math.cos(angleDiff);

            // Target radius with noise and stretch
            const targetRadius = point.baseRadius * stretch + noiseVal * 25;

            // Smooth radius transition
            point.velocity += (targetRadius - point.radius) * 0.15;
            point.velocity *= 0.8;
            point.radius += point.velocity;

            // Slight angle wobble
            point.angle = point.baseAngle + noiseVal * 0.1;
        });
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw multiple layers for glow effect
        this.drawBlob(2.0, this.colors.glow);
        this.drawBlob(1.5, this.colors.tertiary);
        this.drawBlob(1.2, this.colors.secondary);
        this.drawBlob(1.0, this.colors.primary);

        // Draw subtle inner highlight
        this.drawInnerGlow();
    }

    drawBlob(scale, color) {
        const points = this.creature.points;
        const cx = this.creature.x;
        const cy = this.creature.y;

        this.ctx.beginPath();

        // Get positions
        const positions = points.map(p => ({
            x: cx + Math.cos(p.angle) * p.radius * scale,
            y: cy + Math.sin(p.angle) * p.radius * scale
        }));

        // Draw smooth curve through points
        this.ctx.moveTo(
            (positions[positions.length - 1].x + positions[0].x) / 2,
            (positions[positions.length - 1].y + positions[0].y) / 2
        );

        for (let i = 0; i < positions.length; i++) {
            const current = positions[i];
            const next = positions[(i + 1) % positions.length];

            const midX = (current.x + next.x) / 2;
            const midY = (current.y + next.y) / 2;

            this.ctx.quadraticCurveTo(current.x, current.y, midX, midY);
        }

        this.ctx.closePath();

        // Fill with gradient
        const gradient = this.ctx.createRadialGradient(
            cx, cy, 0,
            cx, cy, this.creature.radius * scale * 1.2
        );
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

        this.ctx.fillStyle = gradient;
        this.ctx.fill();
    }

    drawInnerGlow() {
        const cx = this.creature.x;
        const cy = this.creature.y;

        // Subtle pulsing inner glow
        const pulse = Math.sin(this.time * 2) * 0.3 + 0.7;
        const gradient = this.ctx.createRadialGradient(
            cx - 20, cy - 20, 0,
            cx, cy, this.creature.radius * 0.8
        );
        gradient.addColorStop(0, `rgba(255, 255, 255, ${0.03 * pulse})`);
        gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

        this.ctx.beginPath();
        this.ctx.arc(cx, cy, this.creature.radius * 0.6, 0, Math.PI * 2);
        this.ctx.fillStyle = gradient;
        this.ctx.fill();
    }

    animate() {
        if (!this.running) return;

        this.update();
        this.draw();

        requestAnimationFrame(() => this.animate());
    }

    destroy() {
        this.running = false;
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.organicCreature = new OrganicCreature('organic-canvas');
});
