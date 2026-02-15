import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Note: Use 'export' for static hosting (Vercel, etc.)
  // Use 'standalone' for Docker deployments only
  output: process.env.OUTPUT_MODE === 'docker' ? 'standalone' : undefined,
};

export default nextConfig;
