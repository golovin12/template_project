function assignPromotersInit(map, routesData, assignPromoterUrl, csrfToken) {
    const colorMap = {'red': '#dc3545', 'yellow': '#ffc107', 'green': '#28a745'};
    const routeLayers = {};
    const selectedRoutes = new Set();
    const allRouteBounds = L.latLngBounds();

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function updateSelectedUI() {
        const selectedCount = selectedRoutes.size;
        $('#selectedCount').text(selectedCount);

        const selectedList = $('#selectedRoutesList');
        selectedList.empty();

        if (selectedCount === 0) {
            selectedList.html('<li class="list-group-item text-muted text-center py-2">Нет выбранных маршрутов</li>');
            $('#assignButton').prop('disabled', true);
        } else {
            routesData.forEach(route => {
                if (selectedRoutes.has(route.id)) {
                    selectedList.append(`
                        <li class="list-group-item py-2 d-flex justify-content-between align-items-center">
                            <span class="small">${escapeHtml(route.name)}</span>
                            <button class="btn btn-sm btn-link text-danger p-0" onclick="toggleRouteSelection(${route.id})">
                                <span class="material-icons" style="font-size: 16px;">close</span>
                            </button>
                        </li>
                    `);
                }
            });

            const promoterSelected = $('#promoterSelect').val();
            $('#assignButton').prop('disabled', !promoterSelected);
        }
    }

    function showRoutePopup(routeId, layer) {
        const route = routesData.find(r => r.id === routeId);
        if (!route) return;

        const isSelected = selectedRoutes.has(routeId);
        const lastAssignedText = route.last_assigned_date || 'Никогда';

        const popupContent = `
            <div class="route-popup-content">
                <h6 class="mb-2">${escapeHtml(route.name)}</h6>
                <p class="mb-1 small">
                    <span class="text-muted">Последнее назначение:</span><br>
                    <strong>${escapeHtml(lastAssignedText)}</strong>
                </p>
                <button class="btn btn-${isSelected ? 'danger' : 'success'} btn-sm btn-block mt-2"
                        onclick="toggleRouteSelection(${routeId})">
                    ${isSelected ? 'Отменить выбор' : 'Выбрать маршрут'}
                </button>
            </div>
        `;
        layer.bindPopup(popupContent, {maxWidth: 300, minWidth: 200}).openPopup();
    }

    window.toggleRouteSelection = function (routeId) {
        const route = routesData.find(r => r.id === routeId);
        if (!route) return;

        const layer = routeLayers[routeId];
        if (!layer) return;

        const isSelected = selectedRoutes.has(routeId);
        const originalColor = colorMap[route.color] || '#28a745';

        if (isSelected) {
            selectedRoutes.delete(routeId);
            layer.setStyle({color: originalColor, weight: 2, fillOpacity: 0.3});
        } else {
            selectedRoutes.add(routeId);
            layer.setStyle({color: '#007bff', weight: 4, fillOpacity: 0.5});
        }

        updateSelectedUI();
        if (layer.getPopup()) {
            layer.closePopup();
            showRoutePopup(routeId, layer);
        }
    };

    function assignPromoter() {
        const $btn = $('#assignButton');

        const promoterId = $('#promoterSelect').val();
        const routeIds = Array.from(selectedRoutes);

        if (!promoterId || routeIds.length === 0) {
            showNotification('Выберите промоутера и хотя бы один маршрут', 'warning');
            return;
        }

        if (!confirm(`Назначить выбранного промоутера на ${routeIds.length} маршрут(ов)?`)) return;

        $btn.prop('disabled', true);

        $.ajax({
            url: assignPromoterUrl,
            method: 'POST',
            contentType: 'application/json',
            headers: {'X-CSRFToken': csrfToken},
            data: JSON.stringify({route_ids: routeIds, promoter_id: parseInt(promoterId)}),
            success: function (response) {
                if (response.success) {
                    location.reload();
                } else {
                    showNotification(response.error || 'Ошибка при сохранении', 'error');
                    $btn.prop('disabled', false)
                }
            },
            error: function (xhr) {
                const error = xhr.responseJSON?.error || 'Произошла ошибка';
                showNotification('Ошибка: ' + error, 'error');

                $btn.prop('disabled', false);
            }
        });
    }

    function clearSelection() {
        if (selectedRoutes.size === 0) return;

        if (!confirm('Очистить выбор всех маршрутов?')) return;

        selectedRoutes.forEach(routeId => {
            const layer = routeLayers[routeId];
            const route = routesData.find(r => r.id === routeId);
            if (layer && route) {
                const originalColor = colorMap[route.color] || '#28a745';
                layer.setStyle({color: originalColor, weight: 2, fillOpacity: 0.3});
            }
        });

        selectedRoutes.clear();
        updateSelectedUI();
        showNotification('Выбор очищен', 'info');
    }

    routesData.forEach(route => {
        if (!route.polygon || !route.polygon.coordinates) return;

        const color = colorMap[route.color] || '#28a745';

        const layer = L.geoJSON(route.polygon, {
            style: {color: color, weight: 2, fillOpacity: 0.3, opacity: 0.7},
            onEachFeature: (feature, layer) => {
                routeLayers[route.id] = layer;
                if (layer.getBounds) allRouteBounds.extend(layer.getBounds());

                layer.on('click', () => showRoutePopup(route.id, layer));
                layer.on('mouseover', () => layer.setStyle({weight: 4, fillOpacity: 0.5}));
                layer.on('mouseout', () => {
                    const isSelected = selectedRoutes.has(route.id);
                    layer.setStyle({
                        color: isSelected ? '#007bff' : color,
                        weight: isSelected ? 3 : 2,
                        fillOpacity: isSelected ? 0.4 : 0.3
                    });
                });
            }
        }).addTo(map);
    });

    centerMap(map, allRouteBounds);

    $('#promoterSelect').on('change', () => {
        const promoterSelected = $('#promoterSelect').val();
        $('#assignButton').prop('disabled', !promoterSelected || selectedRoutes.size === 0);
    });
    $('#assignButton').on('click', assignPromoter);
    $('#clearSelectionButton').on('click', clearSelection);
}
