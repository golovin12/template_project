function createEfficiencyChart(elementId, labels, efficiencyData) {
    return new Chart(document.getElementById(elementId).getContext("2d"), {
        type: 'bar', data: {
            labels: labels, datasets: [{
                label: "Эффективность (%)", data: efficiencyData, backgroundColor: efficiencyData.map(value => {
                    if (value >= 70) return "rgba(40, 167, 69, 0.7)";
                    if (value >= 40) return "rgba(255, 193, 7, 0.7)";
                    return "rgba(220, 53, 69, 0.7)";
                }), borderColor: efficiencyData.map(value => {
                    if (value >= 70) return "rgba(40, 167, 69, 1)";
                    if (value >= 40) return "rgba(255, 193, 7, 1)";
                    return "rgba(220, 53, 69, 1)";
                }), borderWidth: 2, borderRadius: 4,
            }]
        }, options: {
            responsive: true, maintainAspectRatio: true, plugins: {
                legend: {
                    display: true, labels: {
                        fontSize: 12,
                    }
                }, tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `Эффективность: ${context.parsed.y.toFixed(1)}%`;
                        }
                    }
                }
            }, scales: {
                x: {
                    ticks: {
                        maxRotation: 45, minRotation: 45, font: {size: 10}
                    }
                }, y: {
                    beginAtZero: true, max: 100, ticks: {
                        callback: function (value) {
                            return value + '%';
                        }, font: {size: 10}
                    }, scaleLabel: {
                        display: true, labelString: "Эффективность (%)", font: {size: 12}
                    }
                }
            }
        }
    });
}
