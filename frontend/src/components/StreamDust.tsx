"use client";

import { motion } from "framer-motion";

interface Props {
  active: boolean;
}

const PARTICLES = [
  { x: "10%", y: "45%", delay: 0.1, duration: 3.2, color: "#FFD700", yMove: -15, xMove: 5 },
  { x: "25%", y: "70%", delay: 1.2, duration: 2.8, color: "#A6C1EE", yMove: -12, xMove: -4 },
  { x: "38%", y: "20%", delay: 0.5, duration: 4.1, color: "#FFD700", yMove: -18, xMove: 8 },
  { x: "55%", y: "85%", delay: 1.8, duration: 3.5, color: "#A6C1EE", yMove: -20, xMove: -6 },
  { x: "72%", y: "30%", delay: 0.9, duration: 2.9, color: "#FFD700", yMove: -14, xMove: 4 },
  { x: "85%", y: "60%", delay: 2.1, duration: 3.8, color: "#A6C1EE", yMove: -22, xMove: -3 },
  { x: "15%", y: "80%", delay: 0.4, duration: 3.6, color: "#FFD700", yMove: -16, xMove: 6 },
  { x: "45%", y: "50%", delay: 1.5, duration: 3.0, color: "#A6C1EE", yMove: -10, xMove: -5 },
  { x: "65%", y: "15%", delay: 0.8, duration: 4.5, color: "#FFD700", yMove: -25, xMove: 7 },
  { x: "88%", y: "40%", delay: 2.5, duration: 3.3, color: "#A6C1EE", yMove: -15, xMove: -7 },
];

export function StreamDust({ active }: Props) {
  if (!active) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden rounded-2xl">
      {PARTICLES.map((particle, index) => (
        <motion.span
          key={`dust-${index}`}
          className="absolute h-[3px] w-[3px] rounded-full blur-[0.4px] shadow-[0_0_14px_currentColor]"
          style={{ left: particle.x, top: particle.y, backgroundColor: particle.color }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{
            opacity: [0, 0.8, 0],
            y: [0, particle.yMove],
            x: [0, particle.xMove],
            scale: [0.7, 1.35, 0.8]
          }}
          transition={{
            duration: particle.duration,
            repeat: Infinity,
            repeatType: "loop",
            delay: particle.delay,
            ease: "easeInOut"
          }}
        />
      ))}
      <motion.div
        className="absolute inset-y-[26%] left-[-12%] h-[2px] w-[22%] rounded-full bg-[linear-gradient(90deg,transparent,rgba(255,223,128,0.95),rgba(148,196,255,0.8),transparent)] blur-[1.4px]"
        animate={{ x: ["0%", "520%"], opacity: [0, 0.95, 0] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
