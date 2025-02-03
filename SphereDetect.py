import matplotlib.pyplot as plt

import pandas as pd
import numpy as np
import os

import tifffile as tiff

class SphereDetect:
    """
    A module for detecting spheres in 2D/3D data.
    """
    
    def __init__(self, data):
        """
        Initialize the SphereDetect module with data.
        
        :param data: Input data (e.g., point cloud, image, etc.)
        """
        self.data = data
    
    def preprocess(self, df, channel):
        """
        Perform any necessary preprocessing on the input data.
        """
        df['URL_SphereDetect'] = df[channel].str.split(':').apply(lambda parts: ':'.join(parts[1:]))
        df['Metadata_Z'] = df['FileName_SYTO'].str.extract(r'Z(\d+)C').astype(int) # Extract the Z slice number from the filename, there might be a better way to do this in the CellProfiler pipeline
        df['URL_SphereDetect'] = df['URL_SphereDetect'].str.replace('/share/data/external-datasets/', '/mnt/external-images-pvc/') # This is specific to the way the data is stored in our database
        df['normalized_variance'] = df['URL_SphereDetect'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image)))


        df['normalized_variance'] = df['URL_SphereDetect'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image))) # Calculate the normalized variance for each image

        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
                .assign(d_normalized_variance=lambda x: 
                    x.groupby('Metadata_Well')['normalized_variance'].diff())
        )
        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
                .groupby('Metadata_Well', group_keys=False)
                .apply(self.assign_plane)
        )
        
        return df
    
    def read_image(self, image):
        return tiff.TiffFile(image).asarray()

    def calculate_normalized_variance(self, data):
        return np.var(data) / np.mean(data)
    
    def assign_plane(self, group):
        idxmax = group['d_normalized_variance'].idxmax()
        offset = group.index.get_loc(idxmax)
        
        planes = (np.arange(len(group)) - offset)
        planes = np.where(planes < 0, pd.NA, planes)# Replace negative plane values (i.e. rows before max) with NaN
        
        group['Metadata_Plane'] = pd.Series(planes, index=group.index, dtype='Int64')
        return group

    def detect_spheres(self):
        """
        Detect spheres within the given data.
        
        :return: List of detected spheres (e.g., center coordinates and radius)
        """
        pass
    
    def postprocess(self):
        """
        Apply any post-processing steps to refine detection results.
        """
        pass
    
    def visualize(self, df):
        """
        Visualize detected spheres.
        """

        df = df.sort_values(by='Metadata_Z')
        df_grouped = df.groupby('Metadata_Well')

        # Then plot the normalized variance across Z for each well
        fig, ax = plt.subplots()
        for name, group in df_grouped:
            ax.plot(group['Metadata_Z'], group['d_normalized_variance'], label=name)
        pass
    
    def run(self):
        """
        Run the full sphere detection pipeline.
        """
        cellprofiler_output = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet' # Load the image URLS from here
        channel = 'URL_SYTO'

        df = pd.read_parquet(cellprofiler_output)
        # self.preprocess()
        df = self.preprocess(df, channel)
        # df['URL_SphereDetect'] = df[channel].str.split(':').apply(lambda parts: ':'.join(parts[1:]))
        # df['Metadata_Z'] = df['FileName_SYTO'].str.extract(r'Z(\d+)C').astype(int) # Extract the Z slice number from the filename, there might be a better way to do this in the CellProfiler pipeline
        # df['URL_SphereDetect'] = df['URL_SphereDetect'].str.replace('/share/data/external-datasets/', '/mnt/external-images-pvc/') # This is specific to the way the data is stored in our database
        # df['normalized_variance'] = df['URL_SphereDetect'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image)))


        # df['normalized_variance'] = df['URL_SphereDetect'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image))) # Calculate the normalized variance for each image

        # df = (
        #     df.sort_values(['Metadata_Well', 'Metadata_Z'])
        #         .assign(d_normalized_variance=lambda x: 
        #             x.groupby('Metadata_Well')['normalized_variance'].diff())
        # )
        # df = (
        #     df.sort_values(['Metadata_Well', 'Metadata_Z'])
        #         .groupby('Metadata_Well', group_keys=False)
        #         .apply(self.assign_plane)
        # )

        

        #self.visualize(df)

        results = self.detect_spheres()
        self.postprocess()
        self.visualize()
        return results

# Example usage
if __name__ == "__main__":
    sample_data = None  # Replace with actual data
    detector = SphereDetect(sample_data)
    detected_spheres = detector.run()
    print(detected_spheres)

