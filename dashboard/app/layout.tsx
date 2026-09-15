import React from 'react';
import './globals.css';

export const metadata = {
  title: 'AgentSentrix — 3D Threat Visualizer Dashboard',
  description: 'Real-time security interception, risk evaluation & multi-agent threat visualizer',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-background text-foreground antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
