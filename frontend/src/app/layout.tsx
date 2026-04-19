import "./globals.css";
import type { Metadata } from "next";
import { Cinzel, Inter } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

const cinzel = Cinzel({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "GitaGPT",
  description: "Grounded Bhagavad Gita study assistant"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${cinzel.variable} h-full overflow-hidden font-[var(--font-body)]`}>
        {children}
      </body>
    </html>
  );
}
