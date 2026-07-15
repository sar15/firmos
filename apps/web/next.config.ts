import type { NextConfig } from "next";

const apiOrigin =
  process.env.FIRMOS_API_ORIGIN ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`, // Proxy to FastAPI backend
      },
      {
        source: "/uploads/:path*",
        destination: `${apiOrigin}/uploads/:path*`, // Proxy static uploads to FastAPI
      },
    ];
  },
};

export default nextConfig;
