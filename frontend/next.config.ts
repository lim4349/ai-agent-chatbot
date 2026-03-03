import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Note: Use 'export' for static hosting (Vercel, etc.)
  // Use 'standalone' for Docker deployments only
  output: process.env.OUTPUT_MODE === 'docker' ? 'standalone' : undefined,
  // Proxy API requests to backend
  // - Docker: uses http://backend:8000 (docker-compose service name)
  // - Vercel: uses BACKEND_URL environment variable (set to Render URL)
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
