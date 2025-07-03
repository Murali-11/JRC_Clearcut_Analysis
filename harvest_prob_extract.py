import csv
import os
from qgis.core import QgsProject, QgsRasterLayer, QgsPointXY, QgsGeometry
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator
from PyQt5.QtCore import QVariant

def extract_raster_values_to_csv():
    """
    Extract values from AGB and harvest_probability layers where Harvest layer = 1
    and export to CSV file.
    """
    
    # Get the active project
    project = QgsProject.instance()
    
    # Get the layers by exact name
    agb_layer = None
    harvest_layer = None
    harvest_prob_layer = None
    
    # Find layers in the project by exact name
    for layer_name, layer in project.mapLayers().items():
        if isinstance(layer, QgsRasterLayer):
            layer_display_name = layer.name()
            if layer_display_name == 'AGB_Masked':
                agb_layer = layer
            elif layer_display_name == 'harvest_prob_10m':
                harvest_prob_layer = layer
            elif layer_display_name == 'Harvest_10m':
                harvest_layer = layer
    
    # Check if all layers are found
    if not agb_layer:
        print("Error: AGB_Masked layer not found!")
        return
    if not harvest_layer:
        print("Error: Harvest_10m layer not found!")
        return
    if not harvest_prob_layer:
        print("Error: harvest_prob_10m layer not found!")
        return
    
    print(f"Found layers:")
    print(f"  AGB: {agb_layer.name()}")
    print(f"  Harvest: {harvest_layer.name()}")
    print(f"  Harvest Probability: {harvest_prob_layer.name()}")
    
    # Get raster data providers
    agb_provider = agb_layer.dataProvider()
    harvest_provider = harvest_layer.dataProvider()
    harvest_prob_provider = harvest_prob_layer.dataProvider()
    
    # Get raster extent and resolution
    extent = harvest_layer.extent()
    width = harvest_layer.width()
    height = harvest_layer.height()
    
    # Calculate pixel size
    pixel_size_x = extent.width() / width
    pixel_size_y = extent.height() / height
    
    # Prepare data for CSV
    csv_data = []
    csv_data.append(['X', 'Y', 'AGB_Value', 'Harvest_Probability_Value'])
    
    print("Extracting pixel values...")
    
    # Iterate through all pixels
    for row in range(height):
        if row % 100 == 0:  # Progress indicator
            print(f"Processing row {row} of {height}")
            
        for col in range(width):
            # Calculate world coordinates
            x = extent.xMinimum() + (col + 0.5) * pixel_size_x
            y = extent.yMaximum() - (row + 0.5) * pixel_size_y
            
            # Sample harvest layer value
            harvest_value = harvest_provider.sample(QgsPointXY(x, y), 1)[0]
            
            # Only process if harvest value is 1
            if harvest_value == 1:
                # Sample AGB and harvest probability values
                agb_value = agb_provider.sample(QgsPointXY(x, y), 1)[0]
                harvest_prob_value = harvest_prob_provider.sample(QgsPointXY(x, y), 1)[0]
                
                # Add to CSV data if values are valid (not NoData)
                if (agb_value is not None and harvest_prob_value is not None and 
                    agb_value != agb_provider.sourceNoDataValue(1) and 
                    harvest_prob_value != harvest_prob_provider.sourceNoDataValue(1)):
                    csv_data.append([x, y, agb_value, harvest_prob_value])
    
    # Define output file path - adjust this path as needed
    output_path = os.path.join(os.path.expanduser("~"), "harvest_extraction_results.csv")
    
    # Write to CSV
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        print(f"Successfully exported {len(csv_data)-1} records to: {output_path}")
        
    except Exception as e:
        print(f"Error writing CSV file: {str(e)}")

# Alternative function using numpy for better performance (if you have large rasters)
def extract_raster_values_to_csv_numpy():
    """
    Faster version using numpy arrays - use this for large rasters
    """
    try:
        import numpy as np
    except ImportError:
        print("NumPy not available, using standard method instead")
        extract_raster_values_to_csv()
        return
    
    # Get the active project
    project = QgsProject.instance()
    
    # Get the layers by name
    agb_layer = None
    harvest_layer = None
    harvest_prob_layer = None
    
    for layer_name, layer in project.mapLayers().items():
        if isinstance(layer, QgsRasterLayer):
            layer_display_name = layer.name()
            if layer_display_name == 'AGB_Masked':
                agb_layer = layer
            elif layer_display_name == 'harvest_prob_10m':
                harvest_prob_layer = layer
            elif layer_display_name == 'Harvest_10m':
                harvest_layer = layer
    
    if not all([agb_layer, harvest_layer, harvest_prob_layer]):
        print("Error: One or more layers not found!")
        return
    
    print("Reading raster data into memory...")
    
    # Read raster data as numpy arrays
    harvest_array = harvest_layer.dataProvider().block(1, harvest_layer.extent(), harvest_layer.width(), harvest_layer.height()).data()
    agb_array = agb_layer.dataProvider().block(1, agb_layer.extent(), agb_layer.width(), agb_layer.height()).data()
    harvest_prob_array = harvest_prob_layer.dataProvider().block(1, harvest_prob_layer.extent(), harvest_prob_layer.width(), harvest_prob_layer.height()).data()
    
    # Convert to numpy arrays
    harvest_np = np.frombuffer(harvest_array, dtype=np.float32).reshape(harvest_layer.height(), harvest_layer.width())
    agb_np = np.frombuffer(agb_array, dtype=np.float32).reshape(agb_layer.height(), agb_layer.width())
    harvest_prob_np = np.frombuffer(harvest_prob_array, dtype=np.float32).reshape(harvest_prob_layer.height(), harvest_prob_layer.width())
    
    # Find pixels where harvest = 1
    harvest_mask = harvest_np == 1
    
    # Get extent and pixel size
    extent = harvest_layer.extent()
    pixel_size_x = extent.width() / harvest_layer.width()
    pixel_size_y = extent.height() / harvest_layer.height()
    
    # Get row and column indices where harvest = 1
    rows, cols = np.where(harvest_mask)
    
    # Calculate coordinates and extract values
    csv_data = [['X', 'Y', 'AGB_Value', 'Harvest_Probability_Value']]
    
    for i in range(len(rows)):
        row, col = rows[i], cols[i]
        x = extent.xMinimum() + (col + 0.5) * pixel_size_x
        y = extent.yMaximum() - (row + 0.5) * pixel_size_y
        
        agb_val = agb_np[row, col]
        harvest_prob_val = harvest_prob_np[row, col]
        
        # Check for NoData values
        if not (np.isnan(agb_val) or np.isnan(harvest_prob_val)):
            csv_data.append([x, y, float(agb_val), float(harvest_prob_val)])
    
    # Write to CSV
    output_path = os.path.join(os.path.expanduser("~"), "harvest_extraction_results.csv")
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        print(f"Successfully exported {len(csv_data)-1} records to: {output_path}")
        
    except Exception as e:
        print(f"Error writing CSV file: {str(e)}")

# Run the extraction
if __name__ == "__main__":
    print("Starting raster value extraction...")
    
    # Use the numpy version for better performance, or the standard version if numpy is not available
    extract_raster_values_to_csv_numpy()
    
    print("Extraction complete!")