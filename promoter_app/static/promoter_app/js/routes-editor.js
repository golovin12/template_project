// =====================
// EDITOR INIT
// =====================
function initEditor(map, routesData, saveRoutesUrl, csrfToken) {
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    // =====================
    // STATE
    // =====================
    const layers = [];
    let routeCounter = 0;
    let drawControl = null;

    // =====================
    // HELPERS
    // =====================
    function findLayerIndex(layer) {
        return layers.findIndex(l => l.layer === layer);
    }

    function deleteLayer(layer) {
        const idx = findLayerIndex(layer);
        if (idx === -1) return;

        drawnItems.removeLayer(layer);
        layers[idx].deleted = true;
    }

    function bindPolygonHover(layer) {
        const originalColor = layer.options.color;
        const originalWeight = layer.options.weight;
        const originalFillOpacity = layer.options.fillOpacity;

        layer.on('mouseover', function () {
            layer.setStyle({
                color: '#b700ff',
                weight: 2,
                fillOpacity: 0.3
            });
        });

        layer.on('mouseout', function () {
            layer.setStyle({
                color: originalColor,
                weight: originalWeight,
                fillOpacity: originalFillOpacity
            });
        });
    }

    // проверка перекрытия > threshold (новая зона внутри другой ИЛИ перекрывает другую)
    function isOverlappingTooMuch(newLayer, threshold = 0.9) {
        const newGeo = newLayer.toGeoJSON().geometry;
        const newArea = turf.area(newGeo);

        for (const l of layers) {
            if (l.deleted) continue;
            if (l.layer === newLayer) continue;

            const existingGeo = l.layer.toGeoJSON().geometry;
            const existingArea = turf.area(existingGeo);

            const intersection = turf.intersect(existingGeo, newGeo);

            if (intersection) {
                const intersectionArea = turf.area(intersection);

                const newOverlapRatio = intersectionArea / newArea;
                const existingOverlapRatio = intersectionArea / existingArea;

                if (newOverlapRatio > threshold || existingOverlapRatio > threshold) {
                    return true;
                }
            }
        }

        return false;
    }

    // =====================
    // ADD LAYER UTILITY
    // =====================
    function updateRouteCounter() {
        let maxNum = 0;
        layers.forEach(item => {
            if (!item.deleted && item.name) {
                const match = item.name.match(/Маршрут (\d+)/);
                if (match) {
                    const num = parseInt(match[1]);
                    if (num > maxNum) {
                        maxNum = num;
                    }
                }
            }
        });
        routeCounter = maxNum;
    }

    function addLayer(layer, name = null, id = null) {
        drawnItems.addLayer(layer);
        bindPolygonHover(layer);

        let finalName = name;
        if (finalName === null) {
            routeCounter++;
            finalName = `Маршрут ${routeCounter}`;
        } else {
            finalName = name;
        }

        const item = {id, name: finalName, layer, deleted: false};
        layers.push(item);

        bindPolygon(layer, item);
    }

    // =====================
    // LAYER EDIT
    // =====================
    function enableEditing(layer) {
        const editHandler = drawControl._toolbars.edit._modes.edit.handler;
        editHandler.enable();

        editHandler._featureGroup.eachLayer(l => {
            if (l !== layer && l.editing && l.editing.enabled()) {
                l.editing.disable();
            }
        });

        editHandler._selectedLayer = layer;
    }

    function bindPolygon(layer, item) {
        layer.on('click', function (e) {
            if (drawControl._toolbars.edit._activeMode || drawControl._toolbars.draw._activeMode) {
                return;
            }

            const popup = L.popup()
                .setLatLng(layer.getBounds().getCenter())
                .setContent(`
                    <div style="min-width:180px">
                        <b>Маршрут</b>
                        <input class="form-control form-control-sm mt-2 js-route-name" value="${item.name}">
                        <div class="mt-2 d-flex gap-2">
                            <button class="btn btn-sm btn-primary js-edit">Редактировать</button>
                            <button class="btn btn-sm btn-danger js-delete">Удалить</button>
                        </div>
                    </div>
                `);

            popup.openOn(map);

            const container = popup.getElement();

            container.querySelector('.js-route-name').addEventListener('input', (e) => {
                item.name = e.target.value;
            });

            container.querySelector('.js-edit').addEventListener('click', () => {
                map.closePopup();
                enableEditing(layer);
            });

            container.querySelector('.js-delete').addEventListener('click', () => {
                deleteLayer(layer);
                map.closePopup();
            });
        });
    }

    // =====================
    // LOAD EXISTING ROUTES
    // =====================
    routesData.forEach(route => {
        const latlngs = route.polygon.coordinates.map(
            r => r.map(c => [c[1], c[0]])
        );

        const layer = L.polygon(latlngs);
        addLayer(layer, route.name, route.id);
    });
    updateRouteCounter();

    // =====================
    // FIT
    // =====================
    let bounds;
    if (drawnItems.getLayers().length) {
        bounds = drawnItems.getBounds();
    } else {
        bounds = L.latLngBounds();
    }

    centerMap(map, bounds);

    // =====================
    // DRAW CONTROL
    // =====================
    L.drawLocal.draw.toolbar.actions.title = 'Отменить рисование';
    L.drawLocal.draw.toolbar.actions.text = 'Отмена';
    L.drawLocal.draw.toolbar.finish.title = 'Завершить рисование';
    L.drawLocal.draw.toolbar.finish.text = 'Готово';
    L.drawLocal.draw.toolbar.undo.title = 'Удалить последнюю точку';
    L.drawLocal.draw.toolbar.undo.text = 'Отменить точку';
    L.drawLocal.draw.toolbar.buttons.polyline = 'Нарисовать линию';
    L.drawLocal.draw.toolbar.buttons.polygon = 'Нарисовать полигон';
    L.drawLocal.draw.toolbar.buttons.rectangle = 'Нарисовать прямоугольник';
    L.drawLocal.draw.toolbar.buttons.circle = 'Нарисовать круг';
    L.drawLocal.draw.toolbar.buttons.marker = 'Поставить маркер';
    L.drawLocal.draw.toolbar.buttons.circlemarker = 'Нарисовать круговой маркер';

    L.drawLocal.draw.handlers.circle.tooltip.start = 'Нажмите и тяните, чтобы нарисовать круг.';
    L.drawLocal.draw.handlers.circle.radius = 'Радиус';
    L.drawLocal.draw.handlers.circlemarker.tooltip.start = 'Кликните на карте, чтобы поставить круговой маркер.';
    L.drawLocal.draw.handlers.marker.tooltip.start = 'Кликните на карте, чтобы поставить маркер.';
    L.drawLocal.draw.handlers.polygon.tooltip.start = 'Кликните, чтобы начать рисование фигуры.';
    L.drawLocal.draw.handlers.polygon.tooltip.cont = 'Кликните, чтобы продолжить рисование фигуры.';
    L.drawLocal.draw.handlers.polygon.tooltip.end = 'Кликните на первую точку, чтобы замкнуть фигуру.';
    L.drawLocal.draw.handlers.polyline.error = '<strong>Ошибка:</strong> линии фигуры не могут пересекаться!';
    L.drawLocal.draw.handlers.polyline.tooltip.start = 'Кликните, чтобы начать рисование линии.';
    L.drawLocal.draw.handlers.polyline.tooltip.cont = 'Кликните, чтобы продолжить рисование линии.';
    L.drawLocal.draw.handlers.polyline.tooltip.end = 'Кликните на последнюю точку, чтобы завершить линию.';
    L.drawLocal.draw.handlers.rectangle.tooltip.start = 'Нажмите и тяните, чтобы нарисовать прямоугольник.';
    L.drawLocal.draw.handlers.simpleshape.tooltip.end = 'Отпустите мышь, чтобы завершить рисование.';

    L.drawLocal.edit.toolbar.actions.save.title = 'Сохранить изменения';
    L.drawLocal.edit.toolbar.actions.save.text = 'Сохранить';
    L.drawLocal.edit.toolbar.actions.cancel.title = 'Отменить редактирование, отклонить все изменения';
    L.drawLocal.edit.toolbar.actions.cancel.text = 'Отмена';
    L.drawLocal.edit.toolbar.actions.clearAll.title = 'Удалить все слои';
    L.drawLocal.edit.toolbar.actions.clearAll.text = 'Удалить всё';
    L.drawLocal.edit.toolbar.buttons.edit = 'Редактировать слои';
    L.drawLocal.edit.toolbar.buttons.editDisabled = 'Нет слоёв для редактирования';
    L.drawLocal.edit.toolbar.buttons.remove = 'Удалить слои';
    L.drawLocal.edit.toolbar.buttons.removeDisabled = 'Нет слоёв для удаления';

    L.drawLocal.edit.handlers.edit.tooltip.text = 'Перетаскивайте маркеры или углы, чтобы редактировать фигуры.';
    L.drawLocal.edit.handlers.edit.tooltip.subtext = 'Нажмите "Отмена", чтобы отменить изменения.';
    L.drawLocal.edit.handlers.remove.tooltip.text = 'Кликните на фигуру, чтобы удалить её.';

    drawControl = new L.Control.Draw({
        edit: {featureGroup: drawnItems},
        draw: {
            rectangle: false,
            circle: false,
            marker: false,
            polyline: false,
            circlemarker: false
        }
    });
    map.addControl(drawControl);

    setTimeout(() => {
        const editButton = document.querySelector('.leaflet-draw-edit-edit');
        if (editButton) {
            editButton.style.opacity = '0.5';
            editButton.style.cursor = 'not-allowed';
            editButton.style.pointerEvents = 'none';
            editButton.title = 'Редактирование всех полигонов отключено';
            editButton.setAttribute('disabled', 'disabled');
        }
    }, 100);

    // =====================
    // NEW POLYGON EVENT
    // =====================
    map.on(L.Draw.Event.CREATED, function (e) {
        const layer = e.layer;

        if (isOverlappingTooMuch(layer, 0.8)) {
            showNotification(
                'Ошибка добавления: Новая зона перекрывает более 80% существующей зоны или находится внутри другой зоны.',
                'error'
            );
            return;
        }

        addLayer(layer);
    });

    // =====================
    // EDIT POLYGON EVENT
    // =====================
    map.on(L.Draw.Event.EDITED, function (e) {
        const editHandler = drawControl._toolbars.edit._modes.edit.handler;
        const editedLayer = editHandler._selectedLayer;

        if (!editedLayer) return;

        if (isOverlappingTooMuch(editedLayer, 0.8)) {
            showNotification(
                'Ошибка редактирования: Отредактированная зона перекрывает более 80% существующей зоны или находится внутри другой зоны.\nИзменения отменены.',
                'error'
            );

            if (editHandler && editHandler.revertLayers) {
                editHandler.revertLayers();
            }
            editHandler.disable();
        }
    });

    // =====================
    // DELETE TOOLBAR
    // =====================
    map.on(L.Draw.Event.DELETED, function (e) {
        e.layers.eachLayer(l => deleteLayer(l));
    });

    // =====================
    // SAVE
    // =====================
    $('#saveRoutesBtn').on('click', function () {
        const activeRoutes = layers.filter(l => !l.deleted);

        const confirmSave = confirm(`Вы уверены, что хотите сохранить изменения для всех маршрутов?`);

        if (!confirmSave) {
            return;
        }

        const payload = activeRoutes.map(i => ({
            id: i.id,
            name: i.name,
            polygon: i.layer.toGeoJSON().geometry
        }));

        const $saveBtn = $(this);
        $saveBtn.prop('disabled', true)

        $.ajax({
            url: saveRoutesUrl,
            method: 'POST',
            contentType: 'application/json',
            headers: {'X-CSRFToken': csrfToken},
            data: JSON.stringify({routes: payload}),
            success: function (response) {
                if (response.success) {
                    location.reload();
                } else {
                    showNotification(response.error || 'Ошибка при сохранении', 'error');
                    $saveBtn.prop('disabled', false)
                }
            },
            error: function (xhr) {
                let errorMsg = 'Ошибка при сохранении';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                showNotification(errorMsg, 'error');
                $saveBtn.prop('disabled', false)
            }
        });
    });

    // =====================
    // GPX IMPORT
    // =====================
    document.getElementById('gpxFileInput').addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.gpx')) {
            showNotification('Ошибка: файл должен быть в формате GPX', 'error');
            return;
        }
        e.target.value = '';

        const reader = new FileReader();

        reader.onload = function (ev) {
            try {
                const xml = new DOMParser().parseFromString(ev.target.result, "application/xml");

                const parserError = xml.querySelector('parsererror');
                if (parserError) {
                    showNotification('Ошибка: невалидный XML файл', 'error');
                    e.target.value = '';
                    return;
                }

                const rte = xml.getElementsByTagName("rte");

                if (rte.length === 0) {
                    showNotification('Ошибка: в GPX файле не найдено маршрутов (теги rte)', 'error');
                    e.target.value = '';
                    return;
                }

                let added = 0;
                let hasValidPoints = false;

                function getRouteName(rteElement, index) {
                    const descTag = rteElement.getElementsByTagName('desc');
                    if (descTag.length > 0 && descTag[0].textContent) {
                        const name = descTag[0].textContent.trim();
                        if (name) return name;
                    }
                    return null;
                }

                for (let i = 0; i < rte.length; i++) {
                    const pts = rte[i].getElementsByTagName("rtept");

                    if (pts.length === 0) {
                        console.log(`Маршрут ${i + 1} пропущен: нет точек (rtept)`);
                        continue;
                    }

                    const latlngs = [];
                    let validPoints = true;

                    for (let j = 0; j < pts.length; j++) {
                        const lat = parseFloat(pts[j].getAttribute("lat"));
                        const lon = parseFloat(pts[j].getAttribute("lon"));

                        if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
                            console.log(`Маршрут пропущен: невалидные координаты в точке ${j + 1}`);
                            validPoints = false;
                            break;
                        }

                        latlngs.push([lat, lon]);
                    }

                    if (!validPoints || latlngs.length < 3) {
                        console.log(`Маршрут пропущен: недостаточно валидных точек (нужно минимум 3 для полигона)`);
                        continue;
                    }

                    hasValidPoints = true;
                    const layer = L.polygon(latlngs);
                    let routeName = getRouteName(rte[i], i);

                    if (!isOverlappingTooMuch(layer, 0.9)) {
                        addLayer(layer, routeName);
                        added++;
                    } else {
                        console.log(`Маршрут не добавлен: перекрытие > 90%`);
                    }
                }

                if (!hasValidPoints && rte.length > 0) {
                    showNotification('Ошибка: в файле нет валидных маршрутов (нужны полигоны с 3+ точками)', 'error');
                } else if (added === rte.length) {
                    showNotification(`Добавлено ${added} из ${rte.length} зон`, 'success');
                } else if (added === 0) {
                    showNotification(`Добавлено 0 из ${rte.length} зон (нет валидных или все перекрываются)`, 'error');
                } else {
                    showNotification(`Добавлено ${added} из ${rte.length} зон`, 'warning');
                }

                if (added) {
                    centerMap(map, drawnItems.getBounds());
                }
            } catch (error) {
                console.error('Ошибка при обработке GPX:', error);
                showNotification('Ошибка при обработке файла: неверный формат', 'error');
            }
        };

        reader.onerror = function () {
            showNotification('Ошибка при чтении файла', 'error');
        };

        reader.readAsText(file);
    });
}
