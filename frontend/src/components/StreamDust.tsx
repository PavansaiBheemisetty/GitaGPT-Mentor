"use client";

import { useEffect, useRef } from "react";

interface Props {
  active: boolean;
  cursorRef?: React.RefObject<HTMLSpanElement | null>;
}

/**
 * Tracks the cursor element and emits particles from its position,
 * creating a "divine dust brush painting wisdom" effect.
 * The cursor is rendered as an organic cluster of tiny particles
 * rather than a single circular orb.
 */

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
  maxOpacity: number;
  fadeSpeed: number;
  color: string;
  seed: number;
  age: number;
  lingerFrames: number;
}

const COLORS = [
  "rgba(255, 230, 150,", // Gold
  "rgba(255, 215, 100,", // Warm Gold
  "rgba(180, 210, 255,", // Pale Blue
  "rgba(255, 255, 255,", // White mist
];

export function StreamDust({ active, cursorRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);

  useEffect(() => {
    if (!active) {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();

    // Smooth interpolation variables
    let currentX = -1;
    let currentY = -1;
    let targetX = -1;
    let targetY = -1;

    const animate = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      const canvasRect = canvas.getBoundingClientRect();

      ctx.clearRect(0, 0, w, h);

      if (cursorRef?.current) {
        const cursorRect = cursorRef.current.getBoundingClientRect();
        if (cursorRect.width > 0 && cursorRect.height > 0) {
          targetX = cursorRect.left - canvasRect.left + cursorRect.width / 2;
          targetY = cursorRect.top - canvasRect.top + cursorRect.height / 2;
        }
      }

      // Initialize instantly on first frame
      if (currentX === -1 && targetX !== -1) {
        currentX = targetX;
        currentY = targetY;
      }

      // Smoothly interpolate (lerp) current position towards target
      if (currentX !== -1 && targetX !== -1) {
        // Calmer glide — 10-15% slower than raw tracking
        const lerpFactor = 0.20;

        currentX += (targetX - currentX) * lerpFactor;
        currentY += (targetY - currentY) * lerpFactor;

        // Spawn trail particles at interpolated position
        const dx = targetX - currentX;
        const dy = targetY - currentY;
        const speed = Math.sqrt(dx * dx + dy * dy);

        // Spawn subtle trail particles
        const spawnCount = speed > 2 ? (Math.random() > 0.5 ? 1 : 0) : (Math.random() > 0.8 ? 1 : 0);

        for (let i = 0; i < spawnCount; i++) {
          const op = 0.12 + Math.random() * 0.18;
          particlesRef.current.push({
            x: currentX + (Math.random() - 0.5) * 4,
            y: currentY + (Math.random() - 0.5) * 4,
            vx: (Math.random() - 0.5) * 0.08, // very slow drift
            vy: (Math.random() - 0.5) * 0.08 - 0.03, // barely float up
            radius: 0.4 + Math.random() * 1.2,
            opacity: op,
            maxOpacity: op,
            fadeSpeed: 0.0008 + Math.random() * 0.0006, // slow fade
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
            seed: Math.random() * 100,
            age: 0,
            lingerFrames: 8 + Math.floor(Math.random() * 12), // linger 130-330ms before fading
          });
        }

        // Whisper mist trail: soft dissolving puff left behind
        if (Math.random() > 0.5) {
          particlesRef.current.push({
            x: currentX + (Math.random() - 0.5) * 6,
            y: currentY + (Math.random() - 0.5) * 6,
            vx: 0,
            vy: -0.02,
            radius: 6 + Math.random() * 10,
            opacity: 0.035 + Math.random() * 0.025,
            maxOpacity: 0.06,
            fadeSpeed: 0.0003 + Math.random() * 0.0002, // lingers 800ms-1.2s
            color: COLORS[0],
            seed: Math.random() * 100,
            age: 0,
            lingerFrames: 6 + Math.floor(Math.random() * 8),
          });
        }

        // Draw organic dust cluster at cursor (NOT a single circle)
        // Multiple tiny offset dots with varied opacity = asymmetric, dusty feel
        const t = Date.now() * 0.001;
        const clusterParts = [
          { ox: 0, oy: 0, r: 2, a: 0.25 },
          { ox: Math.sin(t * 1.3) * 3, oy: Math.cos(t * 0.9) * 2.5, r: 1.2, a: 0.18 },
          { ox: Math.sin(t * 0.7 + 2) * 4, oy: Math.cos(t * 1.1 + 1) * 3, r: 1.0, a: 0.12 },
          { ox: Math.sin(t * 1.6 + 4) * 5, oy: Math.cos(t * 0.6 + 3) * 4, r: 0.8, a: 0.08 },
          { ox: Math.cos(t * 0.8) * 3.5, oy: Math.sin(t * 1.4 + 2) * 2, r: 1.4, a: 0.15 },
          { ox: Math.cos(t * 1.2 + 1) * 6, oy: Math.sin(t * 0.5 + 4) * 3.5, r: 0.6, a: 0.06 },
        ];

        for (const cp of clusterParts) {
          const cx = currentX + cp.ox;
          const cy = currentY + cp.oy;

          // Soft glow halo per fragment
          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, cp.r * 5);
          grad.addColorStop(0, `rgba(255, 240, 200, ${cp.a})`);
          grad.addColorStop(0.4, `rgba(255, 230, 150, ${cp.a * 0.3})`);
          grad.addColorStop(1, "rgba(255, 230, 150, 0)");
          ctx.beginPath();
          ctx.arc(cx, cy, cp.r * 5, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();

          // Core dot
          ctx.beginPath();
          ctx.arc(cx, cy, cp.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 240, 210, ${cp.a * 1.2})`;
          ctx.fill();
        }
      }

      // Update and draw particles
      for (let i = particlesRef.current.length - 1; i >= 0; i--) {
        const p = particlesRef.current[i];
        p.x += p.vx;
        // organic wobble
        p.y += p.vy + Math.sin(Date.now() * 0.0015 + p.seed) * 0.06;
        p.age++;

        // Linger phase: hold opacity steady, then begin fading
        if (p.age > p.lingerFrames) {
          p.opacity -= p.fadeSpeed;
        }

        if (p.opacity <= 0) {
          particlesRef.current.splice(i, 1);
          continue;
        }

        // Core glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${p.opacity.toFixed(3)})`;
        ctx.fill();

        // Soft outer glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${(p.opacity * 0.25).toFixed(3)})`;
        ctx.fill();
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas.parentElement!);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      resizeObserver.disconnect();
    };
  }, [active, cursorRef]);

  if (!active) return null;

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 z-0 rounded-2xl"
      aria-hidden="true"
    />
  );
}
