/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  distDir: process.env.COVAL_NEXT_DIST_DIR ?? ".next",
  typescript: {
    tsconfigPath: process.env.COVAL_NEXT_TSCONFIG ?? "tsconfig.json"
  },
  output: "standalone"
};

export default nextConfig;
