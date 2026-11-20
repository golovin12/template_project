class FormsetController {
    // Управление formset (добавление пустой формы, удаление добавленной формы)
    constructor(prefix, cloningData) {
        // cloningData - пустая форма из formset (для создания новых форм)
        this.prefix = prefix  // Префикс набора форм
        this.formset = $(`#formset_${prefix}`)  // Контейнер, в котором расположены формы
        this.addFormsetBtn = $(`#add_form_${prefix}`);  // Кнопка, при нажатии на которую будут добавляться новые формы
        this.cloningFormsetHTML = cloningData
        this.totalFormsetController = $('#id_' + prefix + '-TOTAL_FORMS')
        this.handlers(this)
    }

    handlers(that) {
        that.formset.on('click', '.delete_form', function (e) {
            // Удаление формы
            e.preventDefault();
            that.deleteForm(that, $(this));
            return false;
        });
        that.addFormsetBtn.on('click', function (e) {
            // Добавление формы
            e.preventDefault();
            that.cloneMore();
            return false;
        });
    }

    cloneMore = () => {
        // Клонирует форму устанавливая нужный префикс
        let total = this.totalFormsetController.val();
        let cloningData = this.cloningFormsetHTML.replaceAll("__prefix__", `${total}`)
        this.formset.append(cloningData)

        total++;
        this.totalFormsetController.val(total);
        return false;
    }

    deleteForm(that, btn) {
        // Удаляет последнюю форму. При удалении произвольной нужно во всех формах менять префикс, тогда слетает select2
        let total = parseInt(that.totalFormsetController.val());
        if (total >= 1) {
            let idx = total - 1;
            let forms = $(`.${that.prefix}FormControl`);
            if ($(forms.get(idx)).find(btn).length === 0) {
                showNotification('Можно удалить только последний добавленный элемент!', 'error');
                return false
            }
            btn.parentsUntil(`#formset_${that.prefix}`).remove(`.${that.prefix}FormControl`);
            that.totalFormsetController.val($(`.${that.prefix}FormControl`).length);
        }
        return false;
    }
}
