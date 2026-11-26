$(function () {
    const deviceTypeBranches = JSON.parse(
        document.getElementById('device-type-branches').textContent
    );

    let allBranchOptions = [];
    $('#id_branch option').each(function () {
        let value = $(this).val();
        if (value) {
            allBranchOptions.push({
                value: value,
                text: $(this).text()
            });
        }
    });

    $('#id_device_type').on('change', function () {
        let deviceTypeName = $(this).find('option:selected').text();
        let branchSelect = $('#id_branch');

        let selectedBranchId = branchSelect.val();

        branchSelect.empty().append('<option value="">---------</option>');

        let branchesToAdd = [];

        if (deviceTypeName) {
            let branchesForDevice = deviceTypeBranches[deviceTypeName];

            if (branchesForDevice === 'all') {
                branchesToAdd = allBranchOptions;
            } else if (Array.isArray(branchesForDevice)) {
                branchesToAdd = allBranchOptions.filter(option =>
                    branchesForDevice.includes(parseInt(option.value))
                );
            }
        } else {
            branchesToAdd = allBranchOptions;
        }

        $.each(branchesToAdd, function (_, branch) {
            branchSelect.append(
                $('<option>').val(branch.value).text(branch.text)
            );
        });

        if (selectedBranchId &&
            branchesToAdd.some(branch => String(branch.value) === String(selectedBranchId))
        ) {
            branchSelect.val(selectedBranchId);
        } else if (branchesToAdd.length === 1) {
            branchSelect.val(branchesToAdd[0].value);
        }

        branchSelect.trigger('change');
    }).change();
});
