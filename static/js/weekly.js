const ctx = document.getElementById('progressChart').getContext('2d');

new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [
            {
                label: 'Waist (cm)',
                data: [81, 80.8, 80.6, 80.4, 80.3, 80.2, 80.1],
                borderColor: '#00c6ff',
                backgroundColor: 'rgba(0,198,255,0.2)',
                tension: 0.4
            },
            {
                label: 'Workouts',
                data: [0, 1, 0, 1, 0, 0, 0],
                borderColor: '#00ff99',
                backgroundColor: 'rgba(0,255,153,0.2)',
                tension: 0.4
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#e0e0e0',
                    font: { size: 14, family: '"Segoe UI", sans-serif' }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0,0,0,0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
                padding: 10,
                displayColors: true
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#a0a0a0', font: { size: 12 } }
            },
            y: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#a0a0a0', font: { size: 12 } }
            }
        }
    }
});
