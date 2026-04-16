import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "GitaGPT",
  description: "Grounded Bhagavad Gita study assistant"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
