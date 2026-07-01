import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Coval HeYi",
  description: "Private family health memory demo"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
