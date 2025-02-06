import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import tifffile as tiff



class SphereDetect:
    """
    A module for detecting spheroids in confocal Z-stack image data.
    """
    
    # @David, help: what is the data here exactly? 
    def __init__(self): 
        # The data should be a list of references to images?
        # We need some way of knowing which       
        self.data = None

    # TODO: not sure if all these parameters should be with this function. They should be somewhere though. 
    def load_data(
            self: object, # Should be an object
            regex: str,
            favorite_channel: str,
            cellprofiler_output: str,
            image_path: str, 
            flag: str = 'cellprofiler', 
            offset: int = -2,
            fmin: float = 250,
            ): 
        """ Load relevant images for spheroid detection
        

        Parameters
        ----------
        flag : str, default 'cellprofiler'
            is it a folder you are providing or a cellprofiler output?  
            currently supports one of ['raw_images', 'cellprofiler']
        path_to_images: string? 
            a path to the folder with images #TODO: make it recursive, make it system invariant. 
        regex : 
            pattern that can collect metadata from the images. Only is CellProfiler data is not provided.
        favorite_channel : str, default 'SYTO'
            channel to perform detection on.
        cellprofiler_output : 
            path to cellprofiler output, should take both csv and parquet
        image_path : 
            directory of all your raw images. 
        offset : int, default -2
            value to offset the starting plane. Subtracting 2 works well in our case.
        fmin : float, default 250
            minimum value for the focus score at the maximum change. In practice this will help weed out some non-spheroid images, or poor qualiy spheroids. 
            likely needs to be calibrated for each setup, and assay. 
        """

        # Check what input was given. 
        if flag == 'raw_images': 
            # Data is a filepath
            self.data = self.load_from_images(cellprofiler_output)
            # Do xyz
        elif flag == 'cellprofiler':
            self.data = self.load_from_cp_output(cellprofiler_output)
        else: 
            # There might be a problem 
            print('Error, no correct flag was given')

    #TODO: this is not correct yet. 
    def load_from_images(image_path): 
            # find a list of images recursively from image_path
            image_list = os.listdir(image_path)
            # What should it return here? 

    #TODO: this is not correct yet. 
    def load_from_cp_output(cellprofiler_output):
            df = pd.read_parquet(cellprofiler_output)
            # What should it return here? 

    def preprocess_cellprofiler(self, df, channel):
        """
        Perform any necessary preprocessing on the input data.
        #TODO: make this work on self-data
    
        Requires a Filename_XXX feature as well as a reference to the exact Z-plane
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
    
    #TODO: add the cutoffs here: fmin and offset?. Figure out some better names. 
    def assign_plane(self, group, offset):
        idxmax = group['d_normalized_variance'].idxmax()
        offset_x = group.index.get_loc(idxmax) + offset
        
        planes = (np.arange(len(group)) - offset_x)
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

# Example usage: @David, I do not understand the main part. 
if __name__ == "__main__":
    sample_data = None  # Replace with actual data
    detector = SphereDetect(sample_data)
    detected_spheres = detector.run()
    print(detected_spheres)

