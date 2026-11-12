import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendOrigin = process.env.BACKEND_ORIGIN?.replace(/\/+$/, '');
    return backendOrigin
      ? [
          { source: '/api/sessions', destination: `${backendOrigin}/api/sessions/` },
          { source: '/api/:path*', destination: `${backendOrigin}/api/:path*` },
        ]
      : [];
  },
};

export default nextConfig;
