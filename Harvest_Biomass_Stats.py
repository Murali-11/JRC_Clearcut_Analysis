import os
import csv
import numpy as np
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, 
    QgsFeatureRequest, QgsGeometry, QgsPointXY,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsRasterDataProvider, QgsMessageLog, Qgis
)
from qgis.analysis import QgsZonalStatistics
import processing

def extract_biomass_statistics():
    """
    Extract biomass statistics for each harvest patch and save to CSV.
    
    Configure the input/output paths below before running.
    """
    
    # =============================================================================
    # CONFIGURATION - MODIFY THESE PATHS
    # =============================================================================
    
    # Input layer names (as they appear in QGIS Layers Panel)
    HARVEST_VECTOR_LAYER = "Vectorized"  # Your harvest polygon layer name
    BIOMASS_RASTER_LAYER = "AGB_Masked"   # Your PathFinder AGB raster layer name
    
    # Output CSV file path
    OUTPUT_CSV = r"C:\Users\es24964\Desktop\harvest_biomass_statistics.csv"
    
    # Optional: PathFinder standard deviation layer for uncertainty analysis
    BIOMASS_STDEV_LAYER = None  # Set to layer name if available, e.g., "pathfinder_agb_stdev"
    
    # =============================================================================
    # SCRIPT EXECUTION
    # =============================================================================
    
    try:
        # Load layers from QGIS project
        print("Loading layers...")
        
        # Get harvest vector layer
        harvest_layer = None
        biomass_layer = None
        stdev_layer = None
        
        for layer_name, layer in QgsProject.instance().mapLayers().items():
            if layer.name() == HARVEST_VECTOR_LAYER:
                harvest_layer = layer
            elif layer.name() == BIOMASS_RASTER_LAYER:
                biomass_layer = layer
            elif BIOMASS_STDEV_LAYER and layer.name() == BIOMASS_STDEV_LAYER:
                stdev_layer = layer
        
        # Validate layers
        if not harvest_layer:
            raise Exception(f"Harvest vector layer '{HARVEST_VECTOR_LAYER}' not found in project")
        if not biomass_layer:
            raise Exception(f"Biomass raster layer '{BIOMASS_RASTER_LAYER}' not found in project")
        
        print(f"Found harvest layer: {harvest_layer.featureCount()} features")
        print(f"Found biomass raster: {biomass_layer.width()} x {biomass_layer.height()} pixels")
        
        # Check and align coordinate reference systems
        harvest_crs = harvest_layer.crs()
        biomass_crs = biomass_layer.crs()
        
        if harvest_crs != biomass_crs:
            print(f"CRS mismatch detected. Harvest: {harvest_crs.authid()}, Biomass: {biomass_crs.authid()}")
            print("Transforming coordinates during processing...")
            transform = QgsCoordinateTransform(harvest_crs, biomass_crs, QgsProject.instance())
        else:
            transform = None
        
        # Get raster data provider for pixel value extraction
        provider = biomass_layer.dataProvider()
        
        # Get raster extent and pixel size
        extent = biomass_layer.extent()
        pixel_size_x = biomass_layer.rasterUnitsPerPixelX()
        pixel_size_y = biomass_layer.rasterUnitsPerPixelY()
        pixel_area_ha = (pixel_size_x * pixel_size_y) / 10000  # Convert to hectares
        
        print(f"Raster pixel size: {pixel_size_x:.1f} x {pixel_size_y:.1f} meters")
        print(f"Pixel area: {pixel_area_ha:.4f} hectares")
        
        # Prepare CSV output
        csv_headers = [
            'patch_id', 'feature_id', 'mean_biomass', 'median_biomass', 'std_biomass',
            'min_biomass', 'max_biomass', 'p25_biomass', 'p75_biomass', 'p95_biomass',
            'total_biomass', 'pixel_count', 'effective_area_ha', 'data_coverage_pct'
        ]
        
        if stdev_layer:
            csv_headers.extend(['mean_uncertainty', 'max_uncertainty'])
        
        results = []
        
        # Process each harvest patch
        print("\nProcessing harvest patches...")
        feature_count = harvest_layer.featureCount()
        
        for i, feature in enumerate(harvest_layer.getFeatures()):
            if i % 50 == 0:
                print(f"Processing feature {i+1}/{feature_count}")
            
            try:
                # Get feature geometry
                geom = feature.geometry()
                if transform:
                    geom.transform(transform)
                
                # Get feature identifier
                patch_id = feature.attribute('id') if 'id' in [field.name() for field in feature.fields()] else None
                feature_id = feature.id()
                
                # Extract biomass values using zonal statistics
                biomass_stats = extract_raster_values_in_polygon(
                    biomass_layer, geom, pixel_area_ha
                )
                
                if biomass_stats is None or biomass_stats['pixel_count'] == 0:
                    print(f"Warning: No valid biomass data for feature {feature_id}")
                    continue
                
                # Calculate additional statistics
                values = biomass_stats['values']
                
                # Basic statistics
                stats_result = {
                    'patch_id': patch_id,
                    'feature_id': feature_id,
                    'mean_biomass': float(np.mean(values)),
                    'median_biomass': float(np.median(values)),
                    'std_biomass': float(np.std(values)),
                    'min_biomass': float(np.min(values)),
                    'max_biomass': float(np.max(values)),
                    'p25_biomass': float(np.percentile(values, 25)),
                    'p75_biomass': float(np.percentile(values, 75)),
                    'p95_biomass': float(np.percentile(values, 95)),
                    'total_biomass': float(np.sum(values) * pixel_area_ha),
                    'pixel_count': len(values),
                    'effective_area_ha': float(len(values) * pixel_area_ha),
                    'data_coverage_pct': biomass_stats['coverage_pct']
                }
                
                # Add uncertainty statistics if available
                if stdev_layer:
                    uncertainty_stats = extract_raster_values_in_polygon(
                        stdev_layer, geom, pixel_area_ha
                    )
                    if uncertainty_stats and uncertainty_stats['pixel_count'] > 0:
                        uncertainty_values = uncertainty_stats['values']
                        stats_result['mean_uncertainty'] = float(np.mean(uncertainty_values))
                        stats_result['max_uncertainty'] = float(np.max(uncertainty_values))
                    else:
                        stats_result['mean_uncertainty'] = None
                        stats_result['max_uncertainty'] = None
                
                results.append(stats_result)
                
            except Exception as e:
                print(f"Error processing feature {feature.id()}: {str(e)}")
                continue
        
        # Write results to CSV
        print(f"\nWriting results to {OUTPUT_CSV}")
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"Analysis complete! Processed {len(results)} patches.")
        print(f"Results saved to: {OUTPUT_CSV}")
        
        # Summary statistics
        if results:
            all_means = [r['mean_biomass'] for r in results]
            all_totals = [r['total_biomass'] for r in results]
            
            print(f"\nSummary Statistics:")
            print(f"Average biomass per patch: {np.mean(all_means):.1f} t/ha")
            print(f"Total biomass across all patches: {np.sum(all_totals):.1f} tonnes")
            print(f"Mean patch biomass range: {np.min(all_means):.1f} - {np.max(all_means):.1f} t/ha")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        raise


def extract_raster_values_in_polygon(raster_layer, polygon_geom, pixel_area_ha):
    """
    Extract all raster pixel values within a polygon geometry.
    
    Args:
        raster_layer: QgsRasterLayer object
        polygon_geom: QgsGeometry polygon
        pixel_area_ha: Area of each pixel in hectares
    
    Returns:
        Dictionary with extracted values and statistics
    """
    try:
        # Get raster properties
        provider = raster_layer.dataProvider()
        extent = raster_layer.extent()
        width = raster_layer.width()
        height = raster_layer.height()
        
        pixel_size_x = (extent.xMaximum() - extent.xMinimum()) / width
        pixel_size_y = (extent.yMaximum() - extent.yMinimum()) / height
        
        # Get polygon bounding box
        bbox = polygon_geom.boundingBox()
        
        # Calculate pixel indices for the bounding box
        min_col = max(0, int((bbox.xMinimum() - extent.xMinimum()) / pixel_size_x))
        max_col = min(width - 1, int((bbox.xMaximum() - extent.xMinimum()) / pixel_size_x))
        min_row = max(0, int((extent.yMaximum() - bbox.yMaximum()) / pixel_size_y))
        max_row = min(height - 1, int((extent.yMaximum() - bbox.yMinimum()) / pixel_size_y))
        
        # Extract pixel values
        valid_values = []
        total_pixels = 0
        
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                total_pixels += 1
                
                # Calculate pixel center coordinates
                x = extent.xMinimum() + (col + 0.5) * pixel_size_x
                y = extent.yMaximum() - (row + 0.5) * pixel_size_y
                
                # Check if pixel center is within polygon
                point = QgsPointXY(x, y)
                if polygon_geom.contains(point):
                    # Get pixel value
                    value, success = provider.sample(point, 1)
                    if success and value is not None and not np.isnan(value):
                        # Filter out NoData values (commonly 65535 or 65534 in PathFinder)
                        if value < 65530:  # Assuming values >= 65530 are NoData
                            valid_values.append(value)
        
        if len(valid_values) == 0:
            return None
        
        coverage_pct = (len(valid_values) / total_pixels * 100) if total_pixels > 0 else 0
        
        return {
            'values': np.array(valid_values),
            'pixel_count': len(valid_values),
            'coverage_pct': coverage_pct
        }
        
    except Exception as e:
        print(f"Error extracting raster values: {str(e)}")
        return None


# =============================================================================
# RUN THE ANALYSIS
# =============================================================================

if __name__ == "__main__":
    extract_biomass_statistics()