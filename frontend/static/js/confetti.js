/**
 * Google Antigravity Style Confetti Animation
 * Floating particles that follow cursor with organic 3D-like movement
 */

class AntigravityConfetti {
    constructor() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'confetti-canvas';
        this.canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        `;
        document.body.prepend(this.canvas);

        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
        this.targetMouse = { x: this.mouse.x, y: this.mouse.y };

        // Google-style colors
        this.colors = [
            '#4285F4', // Blue
            '#EA4335', // Red
            '#FBBC04', // Yellow
            '#34A853', // Green
            '#8AB4F8', // Light blue
            '#F28B82', // Light red
            '#FDD663', // Light yellow
            '#81C995', // Light green
            '#C58AF9', // Purple
            '#FF7043', // Orange
        ];

        this.resize();
        this.createParticles();
        this.bindEvents();
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        const count = Math.min(60, Math.floor(window.innerWidth / 25));

        for (let i = 0; i < count; i++) {
            this.particles.push(this.createParticle());
        }
    }

    createParticle() {
        const shapes = ['circle', 'square', 'triangle', 'line'];
        return {
            x: Math.random() * this.canvas.width,
            y: Math.random() * this.canvas.height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 6 + 2,
            color: this.colors[Math.floor(Math.random() * this.colors.length)],
            shape: shapes[Math.floor(Math.random() * shapes.length)],
            rotation: Math.random() * Math.PI * 2,
            rotationSpeed: (Math.random() - 0.5) * 0.02,
            // 3D-like properties
            z: Math.random() * 100,
            zSpeed: (Math.random() - 0.5) * 0.3,
            // Organic floating
            floatOffset: Math.random() * Math.PI * 2,
            floatSpeed: 0.005 + Math.random() * 0.01,
            floatAmplitude: 20 + Math.random() * 30,
            // Mouse interaction
            baseX: 0,
            baseY: 0,
        };
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

    update(time) {
        // Smooth mouse following
        this.mouse.x += (this.targetMouse.x - this.mouse.x) * 0.05;
        this.mouse.y += (this.targetMouse.y - this.mouse.y) * 0.05;

        this.particles.forEach(p => {
            // Store base position for floating
            if (p.baseX === 0) {
                p.baseX = p.x;
                p.baseY = p.y;
            }

            // Organic floating movement
            const floatX = Math.sin(time * p.floatSpeed + p.floatOffset) * p.floatAmplitude * 0.5;
            const floatY = Math.cos(time * p.floatSpeed * 0.7 + p.floatOffset) * p.floatAmplitude;

            // Mouse repulsion/attraction effect
            const dx = p.x - this.mouse.x;
            const dy = p.y - this.mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const maxDist = 200;

            if (dist < maxDist) {
                const force = (1 - dist / maxDist) * 0.5;
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }

            // Apply velocity with damping
            p.vx *= 0.98;
            p.vy *= 0.98;

            // Update position
            p.x += p.vx + floatX * 0.01;
            p.y += p.vy + floatY * 0.01;

            // Z-depth oscillation for 3D effect
            p.z += p.zSpeed;
            if (p.z > 100 || p.z < 0) {
                p.zSpeed *= -1;
            }

            // Rotation
            p.rotation += p.rotationSpeed;

            // Wrap around edges with buffer
            const buffer = 50;
            if (p.x < -buffer) p.x = this.canvas.width + buffer;
            if (p.x > this.canvas.width + buffer) p.x = -buffer;
            if (p.y < -buffer) p.y = this.canvas.height + buffer;
            if (p.y > this.canvas.height + buffer) p.y = -buffer;
        });
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Sort by z-depth for proper layering
        const sorted = [...this.particles].sort((a, b) => a.z - b.z);

        sorted.forEach(p => {
            // Scale and opacity based on z-depth
            const scale = 0.5 + (p.z / 100) * 0.5;
            const opacity = 0.3 + (p.z / 100) * 0.5;
            const size = p.size * scale;

            this.ctx.save();
            this.ctx.translate(p.x, p.y);
            this.ctx.rotate(p.rotation);
            this.ctx.globalAlpha = opacity;
            this.ctx.fillStyle = p.color;
            this.ctx.strokeStyle = p.color;
            this.ctx.lineWidth = 2;

            switch (p.shape) {
                case 'circle':
                    this.ctx.beginPath();
                    this.ctx.arc(0, 0, size, 0, Math.PI * 2);
                    this.ctx.fill();
                    break;

                case 'square':
                    this.ctx.fillRect(-size, -size, size * 2, size * 2);
                    break;

                case 'triangle':
                    this.ctx.beginPath();
                    this.ctx.moveTo(0, -size);
                    this.ctx.lineTo(size, size);
                    this.ctx.lineTo(-size, size);
                    this.ctx.closePath();
                    this.ctx.fill();
                    break;

                case 'line':
                    this.ctx.beginPath();
                    this.ctx.moveTo(-size * 1.5, 0);
                    this.ctx.lineTo(size * 1.5, 0);
                    this.ctx.stroke();
                    break;
            }

            this.ctx.restore();
        });
    }

    animate() {
        const time = performance.now() * 0.001;
        this.update(time);
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.confetti = new AntigravityConfetti();
});
