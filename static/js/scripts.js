document.addEventListener("DOMContentLoaded", () => {
    console.log("Scripts carregados com sucesso!");

    // ===============================
    // Theme Toggle (Claro / Escuro)
    // ===============================
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon   = document.getElementById('theme-icon');
    const html        = document.documentElement;

    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        try { localStorage.setItem('cinnamon-theme', theme); } catch(e) {}
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
        }
        if (themeToggle) {
            themeToggle.title = theme === 'dark' ? 'Mudar para modo claro' : 'Mudar para modo escuro';
        }
    }

    // Inicializa ícone conforme tema atual (já aplicado pelo script inline no <head>)
    const currentTheme = html.getAttribute('data-theme') || 'dark';
    applyTheme(currentTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(next);
        });
    }

    // ===============================
    // Gráfico de Barras - Evolução Patrimônio
    // ===============================
    var optionsPatrimonio = {
        chart: {
            type: 'bar',
            height: 250,
            width: "100%",
            toolbar: { show: false },
            foreColor: '#dcdde1'
        },
        series: [{
            name: 'Patrimônio',
            data: [43.9, 43.9, 44.1, 44.3, 44.7, 44.2]
        }],
        xaxis: {
            categories: ['Dez/24','Jan/25','Fev/25','Mar/25','Abr/25','Mai/25'],
            labels: { style: { fontSize: '11px' } }
        },
        yaxis: {
            labels: {
                style: { fontSize: '11px' },
                formatter: function (val) {
                    return val.toLocaleString("pt-BR", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1
                    });
                }
            }
        },
        plotOptions: {
            bar: {
                borderRadius: 4,
                columnWidth: '45%'
            }
        },
        dataLabels: {
            enabled: true,
            style: { fontSize: '11px', colors: ['#fff'] },
            offsetY: -18,
            formatter: function (val) {
                return val.toLocaleString("pt-BR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1
                });
            }
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toLocaleString("pt-BR", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1
                    });
                }
            }
        },
        grid: {
            borderColor: '#444',
            strokeDashArray: 4
        },
        colors: ['#0984e3']
    };
    if (document.querySelector("#grafico-patrimonio"))
        new ApexCharts(document.querySelector("#grafico-patrimonio"), optionsPatrimonio).render();

    // ===============================
    // Gráfico de Linha - Captação Líquida
    // ===============================
    var optionsCaptacao = {
        chart: {
            type: 'line',
            height: 250,
            width: "100%",
            toolbar: { show: false },
            foreColor: '#dcdde1'
        },
        series: [{
            name: 'Captação Líquida',
            data: [600, 200, 150, 300, 450, 350]
        }],
        xaxis: {
            categories: ['Dez/24','Jan/25','Fev/25','Mar/25','Abr/25','Mai/25'],
            labels: { style: { fontSize: '11px' } }
        },
        yaxis: {
            labels: {
                style: { fontSize: '11px' },
                formatter: function (val) {
                    return val.toLocaleString("pt-BR");
                }
            }
        },
        stroke: {
            curve: 'smooth',
            width: 3
        },
        markers: {
            size: 5,
            colors: ['#1e272e'],
            strokeColors: '#00cec9',
            strokeWidth: 2,
            hover: { size: 7 }
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toLocaleString("pt-BR");
                }
            }
        },
        grid: {
            borderColor: '#444',
            strokeDashArray: 4
        },
        dataLabels: {
            enabled: false
        },
        colors: ['#00cec9']
    };
    if (document.querySelector("#grafico-captacao"))
        new ApexCharts(document.querySelector("#grafico-captacao"), optionsCaptacao).render();

    // ===============================
    // Donut - Patrimônio por Classe de Ativos
    // ===============================
    var optionsClasseAtivos = {
        chart: {
            type: 'donut',
            height: 250,
            width: "100%",
            foreColor: '#dcdde1'
        },
        series: [55, 25, 15, 5],
        labels: ['Recebíveis', 'Caixa', 'Títulos Públicos', 'Outros'],
        colors: ['#0984e3', '#00cec9', '#6c5ce7', '#fdcb6e'],
        legend: {
            position: 'bottom',
            fontSize: '12px'
        },
        plotOptions: {
            pie: { donut: { size: '65%' } }
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toLocaleString("pt-BR", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1
                    }) + " %";
                }
            }
        }
    };
    if (document.querySelector("#grafico-classe-ativos"))
        new ApexCharts(document.querySelector("#grafico-classe-ativos"), optionsClasseAtivos).render();

    // ===============================
    // Donut - Patrimônio por Tipo de Produto
    // ===============================
    var optionsTipoProduto = {
        chart: {
            type: 'donut',
            height: 250,
            width: "100%",
            foreColor: '#dcdde1'
        },
        series: [70, 20, 10],
        labels: ['FIDC', 'FII', 'Outros'],
        colors: ['#55efc4', '#ffeaa7', '#fab1a0'],
        legend: {
            position: 'bottom',
            fontSize: '12px'
        },
        plotOptions: {
            pie: { donut: { size: '65%' } }
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toLocaleString("pt-BR", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1
                    }) + " %";
                }
            }
        }
    };
    if (document.querySelector("#grafico-tipo-produto"))
        new ApexCharts(document.querySelector("#grafico-tipo-produto"), optionsTipoProduto).render();
});
