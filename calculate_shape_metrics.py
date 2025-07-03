import math
import csv
import os
from qgis.core import *
from qgis.utils import *
from PyQt5.QtCore import QVariant
import processing

def calculate_shape_metrics():
    """
    Calculate comprehensive shape metrics for clear cut polygons in QGIS
    and export results to CSV
    """
    
    # Get the active layer (should be your clear cut polygons)
    layer = iface.activeLayer()
    
    if not layer or layer.type() != QgsMapLayer.VectorLayer:
        print("Please select a polygon vector layer")
        return
    
    # Prepare output file path
    output_dir = QgsProject.instance().homePath()
    if not output_dir:
        output_dir = os.path.expanduser("~")
    
    csv_file = os.path.join(output_dir, "clear_cut_shape_metrics.csv")
    
    # Define CSV headers
    headers = [
        'feature_id',
        'area_ha',
        'perimeter_m', 
        'length_m',
        'width_m',
        'equivalent_diameter_m',
        'shape_index',
        'perimeter_area_ratio',
        'compactness_index',
        'fractal_dimension_index',
        'elongation_ratio',
        'orientation_degrees',
        'edge_density'
    ]
    
    # Open CSV file for writing
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            # Process each feature
            for feature in layer.getFeatures():
                if feature.geometry() is None:
                    continue
                
                geom = feature.geometry()
                
                # Skip if not polygon
                if geom.type() != QgsWkbTypes.PolygonGeometry:
                    continue
                
                # Calculate metrics
                metrics = calculate_feature_metrics(feature, geom)
                
                if metrics:
                    writer.writerow(metrics)
                    
        print(f"Shape metrics exported to: {csv_file}")
        print(f"Processed {layer.featureCount()} features")
        
    except Exception as e:
        print(f"Error writing CSV file: {str(e)}")

def calculate_feature_metrics(feature, geom):
    """
    Calculate all shape metrics for a single feature
    """
    try:
        feature_id = feature.id()
        
        # Basic measurements
        area_m2 = geom.area()
        area_ha = area_m2 / 10000.0  # Convert to hectares
        perimeter_m = geom.length()
        
        # Skip very small polygons
        if area_ha < 0.1:
            return None
        
        # Calculate bounding box dimensions
        bbox = geom.boundingBox()
        length_m = max(bbox.width(), bbox.height())
        width_m = min(bbox.width(), bbox.height())
        
        # Equivalent diameter (diameter of circle with same area)
        equivalent_diameter_m = 2 * math.sqrt(area_m2 / math.pi)
        
        # Shape Index (1.0 = perfect circle, >1.0 = increasingly irregular)
        shape_index = perimeter_m / (2 * math.sqrt(math.pi * area_m2))
        
        # Perimeter-to-Area Ratio
        perimeter_area_ratio = perimeter_m / area_m2
        
        # Compactness Index (0-1, where 1 = perfect circle)
        compactness_index = (4 * math.pi * area_m2) / (perimeter_m ** 2)
        
        # Fractal Dimension Index (measures boundary complexity, 1-2 scale)
        if area_m2 > 0 and perimeter_m > 0:
            fractal_dimension_index = 2 * math.log(perimeter_m / 4) / math.log(area_m2)
        else:
            fractal_dimension_index = 0
        
        # Calculate elongation ratio and orientation using minimum bounding ellipse
        elongation_ratio, orientation_degrees = calculate_elongation_and_orientation(geom)
        
        # Edge Density
        edge_density = perimeter_m / area_m2
        
        return [
            feature_id,
            round(area_ha, 4),
            round(perimeter_m, 2),
            round(length_m, 2),
            round(width_m, 2),
            round(equivalent_diameter_m, 2),
            round(shape_index, 4),
            round(perimeter_area_ratio, 6),
            round(compactness_index, 4),
            round(fractal_dimension_index, 4),
            round(elongation_ratio, 4),
            round(orientation_degrees, 2),
            round(edge_density, 6)
        ]
        
    except Exception as e:
        print(f"Error calculating metrics for feature {feature.id()}: {str(e)}")
        return None

def calculate_elongation_and_orientation(geom):
    """
    Calculate elongation ratio and orientation using oriented bounding box
    """
    try:
        # Get the oriented minimum bounding box
        oriented_bbox = geom.orientedMinimumBoundingBox()
        
        if oriented_bbox[0] is None:
            return 1.0, 0.0
        
        # Extract the bounding box geometry
        bbox_geom = oriented_bbox[0]
        
        if bbox_geom.type() != QgsWkbTypes.PolygonGeometry:
            return 1.0, 0.0
        
        # Get the vertices of the bounding box
        vertices = []
        for vertex in bbox_geom.vertices():
            vertices.append([vertex.x(), vertex.y()])
        
        if len(vertices) < 4:
            return 1.0, 0.0
        
        # Calculate side lengths
        side_lengths = []
        for i in range(len(vertices) - 1):
            dx = vertices[i+1][0] - vertices[i][0]
            dy = vertices[i+1][1] - vertices[i][1]
            length = math.sqrt(dx*dx + dy*dy)
            side_lengths.append(length)
        
        if len(side_lengths) < 2:
            return 1.0, 0.0
        
        # Find the two unique side lengths (opposite sides are equal in rectangle)
        unique_lengths = list(set([round(length, 2) for length in side_lengths]))
        
        if len(unique_lengths) < 2:
            return 1.0, 0.0
        
        unique_lengths.sort()
        minor_axis = unique_lengths[0]
        major_axis = unique_lengths[1]
        
        # Calculate elongation ratio
        if minor_axis > 0:
            elongation_ratio = major_axis / minor_axis
        else:
            elongation_ratio = 1.0
        
        # Calculate orientation (angle of major axis from horizontal)
        # Find the longer side for orientation
        max_length = 0
        orientation_angle = 0
        
        for i in range(len(vertices) - 1):
            dx = vertices[i+1][0] - vertices[i][0]
            dy = vertices[i+1][1] - vertices[i][1]
            length = math.sqrt(dx*dx + dy*dy)
            
            if length > max_length:
                max_length = length
                orientation_angle = math.degrees(math.atan2(dy, dx))
        
        # Normalize angle to 0-180 degrees
        if orientation_angle < 0:
            orientation_angle += 180
        
        return elongation_ratio, orientation_angle
        
    except Exception as e:
        print(f"Error calculating elongation and orientation: {str(e)}")
        return 1.0, 0.0

def add_metrics_to_layer():
    """
    Alternative function to add metrics as new fields to the active layer
    """
    layer = iface.activeLayer()
    
    if not layer or layer.type() != QgsMapLayer.VectorLayer:
        print("Please select a polygon vector layer")
        return
    
    # Define new fields
    fields_to_add = [
        QgsField('area_ha', QVariant.Double, 'double', 10, 4),
        QgsField('perimeter_m', QVariant.Double, 'double', 10, 2),
        QgsField('shape_index', QVariant.Double, 'double', 10, 4),
        QgsField('compactness', QVariant.Double, 'double', 10, 4),
        QgsField('elongation', QVariant.Double, 'double', 10, 4),
        QgsField('orientation', QVariant.Double, 'double', 10, 2)
    ]
    
    # Start editing
    layer.startEditing()
    
    # Add fields
    for field in fields_to_add:
        if layer.fields().indexOf(field.name()) == -1:
            layer.addAttribute(field)
    
    layer.updateFields()
    
    # Calculate values for each feature
    for feature in layer.getFeatures():
        if feature.geometry() is None:
            continue
            
        geom = feature.geometry()
        if geom.type() != QgsWkbTypes.PolygonGeometry:
            continue
        
        # Calculate basic metrics
        area_m2 = geom.area()
        area_ha = area_m2 / 10000.0
        perimeter_m = geom.length()
        
        if area_ha >= 0.1:  # Skip very small polygons
            shape_index = perimeter_m / (2 * math.sqrt(math.pi * area_m2))
            compactness = (4 * math.pi * area_m2) / (perimeter_m ** 2)
            elongation_ratio, orientation = calculate_elongation_and_orientation(geom)
            
            # Update feature attributes
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('area_ha'), area_ha)
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('perimeter_m'), perimeter_m)
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('shape_index'), shape_index)
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('compactness'), compactness)
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('elongation'), elongation_ratio)
            layer.changeAttributeValue(feature.id(), layer.fields().indexOf('orientation'), orientation)
    
    # Commit changes
    layer.commitChanges()
    print("Shape metrics added to layer attributes")

# Main execution
print("Starting shape metrics calculation...")
print("Make sure you have selected the clear cut polygon layer")

# Choose which function to run:
# Option 1: Export to CSV
calculate_shape_metrics()

# Option 2: Add fields to layer (uncomment to use instead)
# add_metrics_to_layer()

print("Shape metrics calculation completed!")