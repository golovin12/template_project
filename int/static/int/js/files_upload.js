const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

function initFilesUpload(container) {
    container = $(container)

    if (container.data('files-init')) {
        return
    }

    container.data('files-init', true)

    const input = container.find('.js-files-input')
    const button = container.find('.js-files-btn')
    const preview = container.find('.js-files-preview')
    const hiddenInputs = container.find('.js-files-hidden-inputs')

    const fieldName = input.attr('name')

    let files = []

    button.on('click', function () {
        input.click()
    })

    input.on('change', function () {
        Array.from(this.files).forEach(file => {
            if (file.size > MAX_FILE_SIZE) {
                showNotification(`Файл "${file.name}" больше 10 МБ`, 'error')
                return
            }
            files.push(file)
        })

        renderFiles()
        this.value = ''
    })

    function renderFiles() {
        preview.empty()
        hiddenInputs.empty()

        if (!files.length) {
            preview.addClass('d-none')
            return
        }

        preview.removeClass('d-none')

        files.forEach((file, index) => {
            preview.append(`
                <div class="file-item">
                    <div class="file-info">${file.name} (${formatFileSize(file.size)})</div>
                    <button type="button" class="btn btn-sm btn-outline-danger js-remove-file" data-index="${index}">
                        <i class="material-icons align-bottom">delete</i>
                    </button>
                </div>
            `)

            const hiddenInput = document.createElement('input')

            hiddenInput.type = 'file'
            hiddenInput.name = fieldName
            hiddenInput.classList.add('d-none')

            const dt = new DataTransfer()

            dt.items.add(file)

            hiddenInput.files = dt.files

            hiddenInputs.append(hiddenInput)
        })
    }

    preview.on('click', '.js-remove-file', function () {
        const index = $(this).data('index')
        files.splice(index, 1)
        renderFiles()
    })

    function formatFileSize(bytes) {
        if (bytes === 0) {
            return '0 Bytes'
        }

        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
}

$(function () {
    $('.js-files-upload').each(function () {
        initFilesUpload(this)
    })
})
