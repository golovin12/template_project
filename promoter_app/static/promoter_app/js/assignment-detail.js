function initAssignmentPhotosMap(map, polygonGeojson, photosByLocation, photosWithoutLocation, allPhotos) {
    let currentPhotoIndex = 0;
    let currentPhotoList = [];
    const markers = {};
    const popupPhotoCache = {};

    function openPhotoModal(photoId) {
        const index = allPhotos.findIndex(p => p.id === photoId);
        if (index === -1) return;

        currentPhotoIndex = index;
        currentPhotoList = allPhotos;
        showPhoto(currentPhotoIndex);
    }

    function showPhoto(index) {
        const photo = currentPhotoList[index];
        if (!photo) return;

        currentPhotoIndex = index;

        const modal = $('#photoModal');

        modal.find('img').attr('src', photo.url);
        modal.find('#photoCounter').text(`${index + 1} / ${currentPhotoList.length}`);

        let hasGps = photo.has_location && photo.lat && photo.lng;

        modal.find('#photoInfo').text(`📅 ${photo.created_at}${hasGps ? '' : ' 📍 Нет GPS'}`);

        const container = $('#showOnMapBtnContainer');

        if (hasGps) {
            container.show();
            $('#showOnMapBtn').attr('title', `${photo.lat.toFixed(6)}, ${photo.lng.toFixed(6)}`);
        } else {
            container.hide();
        }

        modal.modal('show');

        modal.find(':focus').blur();
        document.body.focus();
    }

    $('#prevPhoto').on('click', () => {
        if (currentPhotoIndex > 0) showPhoto(currentPhotoIndex - 1);
    });
    $('#nextPhoto').on('click', () => {
        if (currentPhotoIndex < currentPhotoList.length - 1) showPhoto(currentPhotoIndex + 1);
    });

    function highlightPhotos(photoIds) {
        $('.photo-card').removeClass('highlight');
        photoIds.forEach(id => $(`#photo-${id}`).addClass('highlight'));
    }

    function getPopupContent(location, isLoaded) {
        const {lat, lng, photos} = location;
        const locationKey = `${lat.toFixed(6)},${lng.toFixed(6)}`;

        let photosHTML = '';

        if (isLoaded) {
            photosHTML = photos.map(p => `
                <div class="mb-2">
                    <img src="${p.url}" onclick="openPhotoModal(${p.id})" 
                         style="width:100%; border-radius:5px; cursor:pointer;">
                    <small class="text-muted d-block">${p.created_at}</small>
                </div>
            `).join('');
        } else {
            photosHTML = photos.map(p => `
                <div class="mb-2" id="popup-photo-placeholder-${p.id}">
                    <div class="photo-placeholder" style="width:100%; height:120px; background:#f0f0f0; display:flex; align-items:center; justify-content:center; border-radius:5px;">
                        <span class="text-muted">Загрузка...</span>
                    </div>
                    <small class="text-muted d-block">${p.created_at}</small>
                </div>
            `).join('');
        }

        return `
            <div class="marker-popup" data-location-key="${locationKey}">
                <strong>📍 ${photos.length} фото</strong>
                <div class="photo-list mt-2" id="popup-photos-${locationKey}">
                    ${photosHTML}
                </div>
            </div>
        `;
    }

    function loadPopupPhotos(locationKey, photos, marker) {
        if (popupPhotoCache[locationKey]) return;

        popupPhotoCache[locationKey] = true;

        const popup = marker.getPopup();
        const content = getPopupContent({photos, lat: 0, lng: 0}, true);
        popup.setContent(content);

        const container = $(`#popup-photos-${locationKey}`);
        if (!container.length) return;

        container.empty();

        photos.forEach((photo) => {
            container.append(`
                <div class="mb-2">
                    <img src="${photo.url}" onclick="openPhotoModal(${photo.id})" 
                         style="width:100%; border-radius:5px; cursor:pointer;">
                    <small class="text-muted d-block">${photo.created_at}</small>
                </div>
            `);
        });
    }

    function createMarkers() {
        photosByLocation.forEach(location => {
            const {lat, lng, photos} = location;
            const locationKey = `${lat.toFixed(6)},${lng.toFixed(6)}`;

            const marker = L.marker([lat, lng]).addTo(map);
            markers[locationKey] = marker;

            const isLoaded = popupPhotoCache[locationKey] || false;
            marker.bindPopup(getPopupContent(location, isLoaded));

            marker.on('popupopen', function() {
                loadPopupPhotos(locationKey, photos, marker);
                highlightPhotos(photos.map(p => p.id));
            });

            marker.on('popupclose', function() {
                $('.photo-card').removeClass('highlight');
            });

            marker.on('mouseover', () => highlightPhotos(photos.map(p => p.id)));
            marker.on('mouseout', () => $('.photo-card').removeClass('highlight'));
        });
    }

    function drawZone() {
        let bounds;
        if (polygonGeojson?.coordinates) {
            const zone = L.geoJSON(polygonGeojson, {
                style: {color: '#007bff', weight: 3, fillOpacity: 0.2}
            }).addTo(map);
            bounds = zone.getBounds();
        } else {
            bounds = L.latLngBounds();
        }

        centerMap(map, bounds);
    }

    function displayPhotos() {
        const gpsRow = $('#gpsPhotosRow');
        const noGpsRow = $('#photosWithoutGPS');
        gpsRow.empty();
        noGpsRow.empty();

        photosByLocation.forEach(location => {
            location.photos.forEach(photo => {
                gpsRow.append(`
                    <div class="col-6 col-sm-4 col-md-3 col-lg-2 mb-3" id="photo-${photo.id}">
                        <div class="card photo-card h-100" onclick="openPhotoModal(${photo.id})">
                            <img src="${photo.url}" class="card-img-top" loading="lazy">
                            <div class="card-body p-2">
                                <small class="text-muted">${photo.created_at}</small>
                                <span class="badge badge-success float-right">GPS</span>
                            </div>
                        </div>
                    </div>
                `);
            });
        });

        photosWithoutLocation.forEach(photo => {
            noGpsRow.append(`
                <div class="col-6 col-sm-4 col-md-3 col-lg-2 mb-3" id="photo-${photo.id}">
                    <div class="card photo-card h-100" onclick="openPhotoModal(${photo.id})">
                        <img src="${photo.url}" class="card-img-top" loading="lazy">
                        <div class="card-body p-2">
                            <small class="text-muted">${photo.created_at}</small>
                            <span class="badge badge-warning float-right">Нет GPS</span>
                        </div>
                    </div>
                </div>
            `);
        });
    }

    function showPhotoOnMap(photo) {
        if (!photo.has_location || !photo.lat || !photo.lng) return;

        const latKey = photo.lat.toFixed(6);
        const lngKey = photo.lng.toFixed(6);
        const markerKey = `${latKey},${lngKey}`;
        const marker = markers[markerKey];

        if (marker) {
            $('#photoModal').modal('hide');
            $('html, body').animate({
                scrollTop: $(`#map`).offset().top - 20
            }, 500, function () {
                map.setView([photo.lat, photo.lng], 17);
                marker.openPopup();
                const markerElement = marker._icon;
                if (markerElement) {
                    markerElement.classList.add('marker-highlight');
                    setTimeout(() => markerElement.classList.remove('marker-highlight'), 3000);
                }
            });
        }
    }

    $(document).on('click', '#showOnMapBtn', function () {
        const currentPhoto = currentPhotoList[currentPhotoIndex];
        showPhotoOnMap(currentPhoto);
    });

    drawZone();
    createMarkers();
    displayPhotos();

    window.openPhotoModal = openPhotoModal;
}
