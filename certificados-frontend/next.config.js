/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/certificados/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:5000'}/api/certificados/:path*`,
      },
      {
        source: '/api/notificacao/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:5000'}/api/notificacao/:path*`,
      },
      {
        source: '/api/users/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:5000'}/api/users/:path*`,
      },
      {
        source: '/api/relatorios/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:5000'}/api/relatorios/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

