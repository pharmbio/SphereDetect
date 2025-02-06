import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import tifffile as tiff

# --------------------------------------------------------------------------------------------------------------------
# Need to figure out these things: 
# --------------------------------------------------------------------------------------------------------------------

#TODO: Make this work for both types of input. 
# Cellprofiler output
image_path = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet',
# Folder raw images #TODO: find the folder path to raw images that I can access. 
image_path = '/mnt/external-images-pvc/spher-colo52-az/CellPainting_20241220clearedspheroidsBOMI_20241220_151510/AssayPlate_Corning_3830/'

#TODO: Take the following row out of the code. 
df = pd.read_parquet(image_path)
df['URL_SphereDetect'] = df['URL_SphereDetect'].str.replace(
    '/share/data/external-datasets/', 
    '/mnt/external-images-pvc/') # This is specific to the way the data is stored in our database

# TODO: Note somewhere that it would be best to have a metadata indicating slice or section or plane in the cellprofiler output. Fix it beforehand for the example.

# --------------------------------------------------------------------------------------------------------------------

class SphereDetect:
    """
    A module for detecting spheroids in confocal Z-stack image data.
    """
    
    def __init__(self): 
        # TODO: What is data exactly? A list of references to images?    
        self.data = None

    # TODO: What is the data here exactly? I have two types of input, and they should converge to one type of output, 
    #preferably something that can be read by 
    def load_data(
            self: object, # Should be an object
            image_path: str, 
            channel: str, 
            flag: str = 'cellprofiler',
            ): 
        """ Load relevant images for spheroid detection
        """

        # Check what input was given. 
        if flag == 'raw_images': 
            # TODO: Check that instance is a folder with images
            # Data is a filepath
            self.data = self.load_from_images(image_path)
            # TODO: Do xyz
        elif flag == 'cellprofiler':
            #TODO: Check that instance is a parquet or csv file, and that it has a feature called 
            self.data = self.load_from_cp_output(image_path)
        else: 
            # There might be a problem 
            print('Error, no correct flag was given')


    def load_from_images(image_path): 
            """
            contructs a list of images from the folder containing raw images 
            image_path: str, 
                folder path to the raw images
            """
            image_list = []
            for root, dirs, files in os.walk(image_path):
                for x in files:
                     if x.endswith(".tif", ".tiff"): # assuming we have tif files 
                        image_list.append(os.path.join(root, x))
            return image_list

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
    
    # TODO: what is image here ? 
    def read_image(self, image):
        return tiff.TiffFile(image).asarray()

    # TODO: what is data here? 
    def calculate_normalized_variance(self, data):
        return np.var(data) / np.mean(data)
    
    #TODO: add the cutoffs here: fmin and offset?. Figure out some better names. 
    def assign_plane(self, group, offset):
        idxmax = group['d_normalized_variance'].idxmax() # TODO: make this name better
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
    
    def run(
            self: object, # Should be an object
            regex: str,
            channel: str = 'URL_SYTO',
            image_path: str = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet', 
            flag: str = 'cellprofiler', 
            offset: int = -2,
            fmin: float = 250,
            visualize : bool = False,
            ):
        """
        Run the full sphere detection pipeline.

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
        visualize : Boolean, default False
            True or False
        """

        self.load_data(flag, image_path)

        # df = pd.read_parquet(cellprofiler_output)
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
    detected_spheres = detector.run(self)
    print(detected_spheres)

