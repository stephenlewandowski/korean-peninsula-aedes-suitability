// Export the LandScan Mosaic ambient band for the same public 0.25-degree
// Korea-only analysis cells used by analyze_korea_japan.py --scope korea.
//
// Before running:
//   1. Build or upload the 0.25-degree analysis-cell polygons with a stable
//      `cell_id` property matching the suitability tables (for example,
//      r142c1216). `scripts/build_cell_grid_geojson.py --scope korea` creates
//      this public polygon grid from the committed cell-year extract.
//   2. Upload that public regional grid to an Earth Engine asset and replace
//      the placeholder asset below.
//   3. Confirm the collection ordering and band metadata in the Earth Engine
//      Code Editor. The community catalog documents one image per year from
//      1975 through 2024 and the `ambient` band.
//
// The reducer sums the per-pixel ambient-population counts inside each public
// 0.25-degree polygon. This matches the suitability cell footprint, including
// its cell-center country-selection convention; it is not a clipped estimate
// of population inside an administrative border. The export is a
// data-preparation step, not a disease-risk calculation. Review the resulting
// CSV for missing cells, duplicate rows, projection, and units before using
// prepare_population_exposure.py.

var collection = ee.ImageCollection(
  "projects/sat-io/open-datasets/ORNL/LANDSCAN_MOSAIC_TIMESERIES"
);
var analysisCells = ee.FeatureCollection(
  "users/REPLACE_WITH_PUBLIC_KOREA_CELL_GRID_ASSET"
);

// The catalog says the collection has one image per year. Sorting by time and
// assigning 1975 + index avoids depending on an undocumented image property;
// inspect the sorted collection before export and adjust if its order differs.
var images = collection.sort("system:time_start").toList(50);
var years = ee.List.sequence(1975, 2024);

var rows = ee.FeatureCollection(
  years.map(function(year) {
    var index = ee.Number(year).subtract(1975);
    var image = ee.Image(images.get(index)).select("ambient");
    var reduced = image.reduceRegions({
      collection: analysisCells,
      reducer: ee.Reducer.sum(),
      scale: 90,
      crs: "EPSG:4326",
      tileScale: 4
    });
    return reduced.map(function(feature) {
      return ee.Feature(null, {
        cell_id: feature.get("cell_id"),
        year: year,
        ambient_population: feature.get("sum")
      });
    });
  })
).flatten();

Export.table.toDrive({
  collection: rows,
  description: "climademic_korea_landscan_ambient_1975_2024",
  fileNamePrefix: "korea_landscan_population_by_cell_year",
  fileFormat: "CSV",
  selectors: ["cell_id", "year", "ambient_population"]
});
