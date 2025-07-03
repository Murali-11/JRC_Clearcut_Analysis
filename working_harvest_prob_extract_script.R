library(terra)
library(readr)

# Set file paths
harvest_file <- "C:/Users/es24964/Documents/JRC_Desktop/clipped_harvest2021_10m.tif"
biomass_file <- "C:/Users/es24964/Documents/JRC_Desktop/AGB_Masked.tif"
forest_type_file <- "C:/Users/es24964/Documents/JRC_Desktop/FTY_Masked.tif"
harvest_prob_file <- "C:/Users/es24964/Documents/JRC_Desktop/harvest_prob_2021_clipped_10m.tif"
output_file <- "C:/Users/es24964/Documents/JRC_Desktop/harvest_pixels_analysis.csv"

cat("=== REPLICATING PYTHON APPROACH IN R ===\n")

# Read rasters
harvest_raster <- rast(harvest_file)
biomass_raster <- rast(biomass_file)
forest_type_raster <- rast(forest_type_file)
harvest_prob_raster <- rast(harvest_prob_file)

# Find harvest pixels using the same approach as Python
# Convert to matrix/array format (like Python numpy arrays)
harvest_data <- as.matrix(harvest_raster, wide = TRUE)
biomass_data <- as.matrix(biomass_raster, wide = TRUE)
forest_data <- as.matrix(forest_type_raster, wide = TRUE)
harvest_prob_data <- as.matrix(harvest_prob_raster, wide = TRUE)

cat("Raster dimensions:\n")
cat("Harvest:", dim(harvest_data), "\n")
cat("Biomass:", dim(biomass_data), "\n")
cat("Forest:", dim(forest_data), "\n")

# Find harvest locations (harvest == 1)
harvest_mask <- harvest_data == 1
harvest_locations <- which(harvest_mask, arr.ind = TRUE)

cat("Found", nrow(harvest_locations), "harvest pixels\n")

if(nrow(harvest_locations) > 0) {
  # Extract values at harvest locations
  biomass_values <- biomass_data[harvest_mask]
  forest_values <- forest_data[harvest_mask]
  harvest_prob_values <- harvest_prob_data[harvest_mask]
  
  cat("Extracted values:\n")
  cat("Biomass range:", range(biomass_values, na.rm = TRUE), "\n")
  cat("Forest type values:", unique(forest_values), "\n")
  cat("Harvest prob range:", range(harvest_prob_values, na.rm = TRUE), "\n")
  
  # Create data frame (replicating Python approach)
  df <- data.frame(
    biomass = biomass_values,
    forest_type_numeric = forest_values,
    harvest_probability = harvest_prob_values
  )
  
  # Convert forest type names
  df$forest_type <- ifelse(df$forest_type_numeric == 1, "broadleaf", 
                           ifelse(df$forest_type_numeric == 2, "conifer", "unknown"))
  
  cat("\nBefore filtering:", nrow(df), "rows\n")
  
  # Clean data (following Python script)
  df_clean <- df[df$biomass > 0 & df$forest_type != "unknown", ]
  
  cat("After filtering (biomass > 0, forest_type != unknown):", nrow(df_clean), "rows\n")
  
  if(nrow(df_clean) > 0) {
    # Apply your additional filters
    df_final <- df_clean[
      df_clean$biomass >= 1 & 
        df_clean$biomass <= 800 & 
        !is.na(df_clean$harvest_probability), 
    ]
    
    cat("After AGB 1-800 filter:", nrow(df_final), "rows\n")
    
    # Remove numeric forest type column
    df_final$forest_type_numeric <- NULL
    
    # Save results
    write_csv(df_final, output_file)
    
    # Show summary
    cat("\nFinal Summary:\n")
    cat("Forest types:\n")
    print(table(df_final$forest_type))
    cat("Biomass range:", min(df_final$biomass), "to", max(df_final$biomass), "\n")
    cat("Harvest prob range:", min(df_final$harvest_probability), "to", max(df_final$harvest_probability), "\n")
    cat("Final dataset:", nrow(df_final), "rows\n")
    cat("Saved to:", output_file, "\n")
  }
}