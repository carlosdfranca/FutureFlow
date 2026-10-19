/**
 * Seleção de títulos via checkbox para gerar CNAB de baixa.
 * Usado em detalhe_cessao.html e listar_titulos.html: liga o checkbox
 * "selecionar todos" aos checkboxes de linha (name="titulos") e
 * habilita/desabilita o botão "Gerar CNAB de Baixa" do form correspondente
 * conforme há ou não alguma seleção.
 */
(function () {
    function atualizarBotao(form) {
        if (!form) return;
        var algumSelecionado = form.querySelectorAll('.js-selecionar-titulo:checked').length > 0;
        form.querySelectorAll('button[type="submit"].js-btn-cnab-baixa').forEach(function (btn) {
            btn.disabled = !algumSelecionado;
        });
    }

    document.querySelectorAll('.js-selecionar-todos').forEach(function (master) {
        var form = document.getElementById(master.dataset.form);
        if (!form) return;
        master.addEventListener('change', function () {
            form.querySelectorAll('.js-selecionar-titulo').forEach(function (cb) {
                cb.checked = master.checked;
            });
            atualizarBotao(form);
        });
    });

    document.querySelectorAll('.js-selecionar-titulo').forEach(function (cb) {
        cb.addEventListener('change', function () {
            var form = document.getElementById(cb.dataset.form);
            atualizarBotao(form);
        });
    });
}());
