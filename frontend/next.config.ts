import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Note: Use 'export' for static hosting (Vercel, etc.)
  // Use 'standalone' for Docker deployments only
  output: process.env.OUTPUT_MODE === 'docker' ? 'standalone' : undefined,
  // Proxy API requests to backend in Docker environment
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
