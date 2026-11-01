// ═══════════════════════════════════════════════════════════════
// NEO AI — PM2 Ecosystem Config for TRAININGBOT2
// Run: pm2 start ecosystem.config.js
// Then: pm2 startup && pm2 save
// ═══════════════════════════════════════════════════════════════

module.exports = {
  apps: [
    {
      name: 'neo-ai-api',
      script: 'gunicorn',
      args: '-w 4 -b 0.0.0.0:8000 --timeout 120 --keep-alive 5 --access-logfile - --error-logfile - wsgi:app',
      interpreter: 'python3',
      cwd: '/home/ubuntu/TRAININGBOT2',

      // Process management
      instances: 1,
      exec_mode: 'fork',

      // Auto-restart
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',

      // Environment
      env: {
        NODE_ENV: 'production',
        NEO_API_HOST: '0.0.0.0',
        NEO_API_PORT: '8000',
        NEO_DEBUG: 'false',
        PYTHONDONTWRITEBYTECODE: '1',
        PYTHONUNBUFFERED: '1',
      },

      // Logging
      log_file: '/home/ubuntu/TRAININGBOT2/logs/combined.log',
      out_file: '/home/ubuntu/TRAININGBOT2/logs/out.log',
      err_file: '/home/ubuntu/TRAININGBOT2/logs/error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,

      // Monitoring
      watch: false,
      ignore_watch: ['node_modules', 'logs', 'data', '__pycache__', '*.pyc'],

      // Resource limits
      max_memory_restart: '2G',

      // Graceful shutdown
      kill_timeout: 5000,
      listen_timeout: 8000,
    },

    // Optional: Ollama service monitor
    {
      name: 'neo-ollama',
      script: 'docker',
      args: 'start -a ollama',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 5,
    },
  ],

  // Deployment config (for pm2 deploy)
  deploy: {
    production: {
      user: 'ubuntu',
      host: 'your-oracle-ip',
      ref: 'origin/main',
      repo: 'git@github.com:yourusername/TRAININGBOT2.git',
      path: '/home/ubuntu/TRAININGBOT2',
      'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production',
    },
  },
};
