import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArthaTwin — Living Money Model",
  description: "A deterministic-first personal finance coach.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
