import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // web/'in bir üstündeki journal/ klasörünü Vercel'in serverless
  // fonksiyon paketine dahil et — yoksa canlıda journal okunamaz.
  outputFileTracingRoot: path.join(__dirname, ".."),
  outputFileTracingIncludes: {
    "/*": ["../journal/**/*"],
  },
};

export default nextConfig;
