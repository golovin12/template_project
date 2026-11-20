// =====================
// MAP INIT
// =====================
function initMap(tilesApiKey) {
    const crsYandex = new L.Proj.CRS(
        'EPSG:3395',
        '+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
        {
            origin: [-20037508.342789244, 20037508.342789244],
            resolutions: [156543.033928, 78271.516964, 39135.758482, 19567.879241, 9783.9396205, 4891.96981025, 2445.984905125, 1222.9924525625, 611.49622628125, 305.748113140625, 152.8740565703125, 76.43702828515625, 38.218514142578125, 19.109257071289062, 9.554628535644531, 4.777314267822266, 2.388657133911133, 1.194328566955566, 0.597164283477783, 0.298582141738892]
        }
    );

    const map = L.map('map', {
        crs: crsYandex,
        attributionControl: false
    });

    L.tileLayer(
        `https://tiles.api-maps.yandex.ru/v1/tiles/?x={x}&y={y}&z={z}&lang=ru_RU&l=map&apikey=${tilesApiKey}`,
        {
            tileSize: 256,
            attribution: ''
        }
    ).addTo(map);

    return map;
}

function centerMap(map, bounds = L.latLngBounds()) {
    if (bounds.isValid()) {
        map.fitBounds(bounds, {padding: [20, 20]});
    } else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                map.setView([position.coords.latitude, position.coords.longitude], 14);
            },
            () => {
                map.setView([55.751244, 37.618423], 11);
            },
            {enableHighAccuracy: true, timeout: 5000}
        );
    } else {
        map.setView([55.751244, 37.618423], 11);
    }
}
