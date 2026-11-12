import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import "./globals.css";
import "@/components/shipments/view-transitions.global.css";

export const metadata: Metadata = {
  title: "Smart Caspian Transit",
  description: "Прототип логистической платформы коридора Север — Юг",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
