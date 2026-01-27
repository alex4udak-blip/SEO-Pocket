/**
 * Particles Animation - Google Antigravity Style
 * Canvas 2D with physics simulation
 */

class Particle {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');

        // Position
        this.x = options.x || Math.random() * canvas.width;
        this.y = options.y || Math.random() * canvas.height;

        // Velocity
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;

        // Properties
        this.radius = options.radius || Math.random() * 2 + 1;
        this.baseRadius = this.radius;
        this.color = options.color || this.getRandomColor();
        this.alpha = options.alpha || Math.random() * 0.5 + 0.3;

        // Physics
        this.mass = this.radius * 0.1;
        this.friction = 0.99;
        this.gravity = 0;

        // Mouse interaction
        this.mouseDistance = 0;
        this.isHovered = false;
    }

    getRandomColor() {
        const colors = [
            '#4285f4', // Google Blue
            '#ea4335', // Google Red
            '#fbbc05', // Google Yellow
            '#34a853', // Google Green
            '#7c4dff', // Purple
            '#00bcd4', // Cyan
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    update(mouse, particles) {
        // Mouse repulsion
        if (mouse.x !== null && mouse.y !== null) {
            const dx = this.x - mouse.x;
            const dy = this.y - mouse.y;
            this.mouseDistance = Math.sqrt(dx * dx + dy * dy);

            const maxDistance = 150;
            if (this.mouseDistance < maxDistance) {
                const force = (maxDistance - this.mouseDistance) / maxDistance;
                const angle = Math.atan2(dy, dx);

                this.vx += Math.cos(angle) * force * 0.5;
                this.vy += Math.sin(angle) * force * 0.5;

                // Grow when near mouse
                this.radius = this.baseRadius + force * 3;
                this.isHovered = true;
            } else {
                this.radius = this.baseRadius;
                this.isHovered = false;
            }
        }

        // Apply velocity
        this.x += this.vx;
        this.y += this.vy;

        // Apply friction
        this.vx *= this.friction;
        this.vy *= this.friction;

        // Bounce off edges
        if (this.x < this.radius) {
            this.x = this.radius;
            this.vx *= -0.8;
        }
        if (this.x > this.canvas.width - this.radius) {
            this.x = this.canvas.width - this.radius;
            this.vx *= -0.8;
        }
        if (this.y < this.radius) {
            this.y = this.radius;
            this.vy *= -0.8;
        }
        if (this.y > this.canvas.height - this.radius) {
            this.y = this.canvas.height - this.radius;
            this.vy *= -0.8;
        }

        // Subtle random movement
        this.vx += (Math.random() - 0.5) * 0.02;
        this.vy += (Math.random() - 0.5) * 0.02;
    }

    draw() {
        this.ctx.beginPath();
        this.ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        this.ctx.fillStyle = this.color;
        this.ctx.globalAlpha = this.isHovered ? 0.9 : this.alpha;
        this.ctx.fill();
        this.ctx.globalAlpha = 1;

        // Glow effect
        if (this.isHovered) {
            this.ctx.beginPath();
            this.ctx.arc(this.x, this.y, this.radius * 2, 0, Math.PI * 2);
            const gradient = this.ctx.createRadialGradient(
                this.x, this.y, this.radius * 0.5,
                this.x, this.y, this.radius * 2
            );
            gradient.addColorStop(0, this.color + '40');
            gradient.addColorStop(1, 'transparent');
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
        }
    }
}

class ParticleSystem {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Canvas not found:', canvasId);
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: null, y: null };
        this.isRunning = false;

        // Options
        this.options = {
            particleCount: options.particleCount || 80,
            connectDistance: options.connectDistance || 120,
            lineWidth: options.lineWidth || 0.5,
            backgroundColor: options.backgroundColor || '#0a0a0f',
            ...options
        };

        this.init();
    }

    init() {
        this.resize();
        this.createParticles();
        this.bindEvents();
        this.start();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        this.particles = [];
        for (let i = 0; i < this.options.particleCount; i++) {
            this.particles.push(new Particle(this.canvas));
        }
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
            this.createParticles();
        });

        this.canvas.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });

        // Touch support
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            this.mouse.x = e.touches[0].clientX;
            this.mouse.y = e.touches[0].clientY;
        });

        this.canvas.addEventListener('touchend', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
    }

    drawConnections() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const p1 = this.particles[i];
                const p2 = this.particles[j];

                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.options.connectDistance) {
                    const alpha = (1 - distance / this.options.connectDistance) * 0.3;

                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);

                    // Gradient line
                    const gradient = this.ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
                    gradient.addColorStop(0, p1.color + Math.floor(alpha * 255).toString(16).padStart(2, '0'));
                    gradient.addColorStop(1, p2.color + Math.floor(alpha * 255).toString(16).padStart(2, '0'));

                    this.ctx.strokeStyle = gradient;
                    this.ctx.lineWidth = this.options.lineWidth;
                    this.ctx.stroke();
                }
            }
        }
    }

    animate() {
        if (!this.isRunning) return;

        // Clear canvas
        this.ctx.fillStyle = this.options.backgroundColor;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Update and draw particles
        for (const particle of this.particles) {
            particle.update(this.mouse, this.particles);
        }

        // Draw connections
        this.drawConnections();

        // Draw particles
        for (const particle of this.particles) {
            particle.draw();
        }

        requestAnimationFrame(() => this.animate());
    }

    start() {
        this.isRunning = true;
        this.animate();
    }

    stop() {
        this.isRunning = false;
    }

    // Explosion effect when analyzing
    explode(x, y) {
        const explosionParticles = 20;
        for (let i = 0; i < explosionParticles; i++) {
            const angle = (Math.PI * 2 / explosionParticles) * i;
            const speed = 5 + Math.random() * 5;
            const particle = new Particle(this.canvas, {
                x: x,
                y: y,
                radius: 3 + Math.random() * 3
            });
            particle.vx = Math.cos(angle) * speed;
            particle.vy = Math.sin(angle) * speed;
            this.particles.push(particle);
        }

        // Remove extra particles after animation
        setTimeout(() => {
            while (this.particles.length > this.options.particleCount) {
                this.particles.shift();
            }
        }, 2000);
    }
}

// Export for use
window.ParticleSystem = ParticleSystem;
