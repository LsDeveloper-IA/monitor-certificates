import type { NextConfig } from "next";

const staticExport = process.env.NEXT_STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? {
      // Usado pelo pacote portatil: o Flask serve os arquivos gerados em out/.
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : {
      async rewrites() {
        const backend = process.env.BACKEND_URL || "http://localhost:5000";
        return [
          {
            source: "/api/certificados/:path*",
            destination: `${backend}/api/certificados/:path*`,
          },
          {
            source: "/api/users/:path*",
            destination: `${backend}/api/users/:path*`,
          },
          {
            source: "/api/relatorios/:path*",
            destination: `${backend}/api/relatorios/:path*`,
          },
          // Automacao, notificacao e WhatsContabil passam pelos Route
          // Handlers em src/app/api, que validam a chave e identificam o
          // proxy local antes de chamar o Flask.
          {
            source: "/api/historico/:path*",
            destination: `${backend}/api/historico/:path*`,
          },
          {
            source: "/api/configuracao/:path*",
            destination: `${backend}/api/configuracao/:path*`,
          },
        ];
      },
    };

export default nextConfig;
