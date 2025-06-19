module.exports = {
  apps: [
    {
      name: "scola-absen",             // Nama aplikasi
      script: "absensi.py",                // File utama python
      interpreter: "python3",          // Gunakan Python 3
      watch: true,                    // true jika ingin auto-reload saat file berubah
      max_restarts: 10,                // Restart maksimal 10 kali jika crash
      restart_delay: 5000,             // Delay 5 detik antar restart
      error_file: "logs/err.log",      // File log error
      out_file: "logs/out.log",        // File log output
      log_date_format: "YYYY-MM-DD HH:mm:ss",  // Format waktu log
      env: {
        ENV: "development"
      },
      env_production: {
        ENV: "production"
      }
    }
  ]
}
