import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // typedRoutes disabled: every <Link href={dynamicString}> and
  // router.replace(templateString) call fails TS2322 ("Type 'string' is
  // not assignable to type 'RouteImpl<string>'"). The cost of casting
  // every dynamic navigation site outweighs the benefit of catching typos
  // in literal route strings. Re-enable when the codebase has zero
  // dynamic-href call sites.
  // experimental: { typedRoutes: true },
  transpilePackages: ["@ai-news-scraper/shared"],
  async rewrites() {
    const apiUrl = process.env.API_INTERNAL_URL || "http://localhost:8082";
    return [{ source: "/api/backend/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
