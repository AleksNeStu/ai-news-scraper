import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: true,
  },
  transpilePackages: ["@ai-news-scraper/shared"],
  async rewrites() {
    const apiUrl = process.env.API_INTERNAL_URL || "http://localhost:8082";
    return [{ source: "/api/backend/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
