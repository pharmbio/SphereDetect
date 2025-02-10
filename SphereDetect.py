import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import tifffile as tiff
import re

# --------------------------------------------------------------------------------------------------------------------
# Need to figure out these things: 
# --------------------------------------------------------------------------------------------------------------------
"""
# Cellprofiler output & raw images
image_path = '/home/jovyan/share/data/analyses/christa/SphereDetect/cp_output.parquet',
image_path = '/mnt/external-images-pvc/spher-colo52-az/CellPainting_20241220clearedspheroidsBOMI_20241220_151510/AssayPlate_Corning_3830/'

#TODO: Make a normal setlist with Cellprofiler and see how it looks? --> Impossible to run it on thinlinc, as of now I am missing a lot of data. 

"""
# --------------------------------------------------------------------------------------------------------------------

class SphereDetect:
    """
    A module for detecting spheroids in confocal Z-stack image data.
    """
    
    def __init__(self): 
        self.data = None
        self.results = None


    def load_data(
            self: object,
            image_path: str,
            regex: str = None, 
            channel: str = None, 
            flag: str = 'cellprofiler',
            z_info : str = 'Metadata_Plane'
            ): 
        """ Load relevant images for spheroid detection
        """

        # Option 1: Load from raw images
        if os.path.isdir(image_path):
            if regex is None:
                raise ValueError("For folder-based loading, you must specify a 'regex'.")
            self.data = self.load_from_images(image_path, regex)
    
        # Option 2: Load from CellProfiler output
        else:
            if not os.path.isfile(image_path):
                raise ValueError(f"'{image_path}' is not a valid file or directory.")
            
            valid_extensions = {".csv", ".parquet"}
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext not in valid_extensions:
                raise ValueError(
                    f"Expected a CSV or parquet file (.csv/.parquet), got '{file_ext}' for '{image_path}'."
                )
            
            if channel is None:
                raise ValueError("For CellProfiler outputs, you must specify a 'channel'.")
        
            self.data = self.load_from_cp_output(image_path, channel, z_info)

        assert self.data is not None, "The data is not loaded"

    def load_from_images(self, image_path, regex): 
            """
            contructs a list of images from the folder containing raw images 
            image_path: str, 
                folder path to the raw images
            """
            image_list = []
            for root, dirs, files in os.walk(image_path):
                for x in files:
                     if x.endswith((".tif", ".tiff")) and re.search(regex, x) : # assuming we have tif files and we match the regex
                        image_list.append(os.path.join(root, x))

            df = pd.DataFrame(image_list, columns=['image_path'])
            df[["Metadata_Well", "Metadata_Z"]] = df['image_path'].str.extract(regex).reset_index(drop=True) 
            df["Metadata_Z"] = df["Metadata_Z"].astype(int) 
            return df

    def load_from_cp_output(self, image_path, channel, z_info):

        if image_path.endswith(".csv"):
            df = pd.read_csv(image_path)

        elif image_path.endswith(".parquet"):
            df = pd.read_parquet(image_path)

        assert df is not None, "The dataframe is not loaded"

        if f'PathName_{channel.upper()}' not in df.columns:
            raise ValueError("The column f'PathName_{channel.upper()}' is not present in the dataframe")

        # TODO: Actually need to join PathName with FileName, and then extract the well and Z information
        df = df.rename(columns={f'PathName_{channel.upper()}': 'image_path'})
        df['Metadata_Z'] = df[z_info].astype(int)
        df = df[['image_path','Metadata_Well', 'Metadata_Z']].reset_index(drop=True)
        pass
        # return df

    def detect_spheres(self, offset, fmin):
        """
        Detect spheroids in the image data, assign a plane number to each image, and filter out wells that do not meet the minimum focus score.
        """

        df = self.data

        # Calculate the normalized variance for each image
        df['normalized_variance'] = df['image_path'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image))) 

        # Caluclate the differential normalized variance
        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
                .assign(delta_normalized_variance=lambda x: 
                    x.groupby('Metadata_Well')['normalized_variance'].diff())
        )

        # Assign the plane number to each image
        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
            .groupby('Metadata_Well', group_keys=False)
            .apply(lambda group: self.assign_plane(group, offset))
        )

        # # Assign the plane number to each image
        # self.assign_plane(df, offset) #TODO: Do I need one more function for this?

        # Filter out wells that do not meet the minimum focus score
        self.postprocess(df, fmin)
        assert df is not None, "The dataframe is not loaded"
        self.result = df
    
    def read_image(self, image):
        with tiff.TiffFile(image) as tf:
            data = tf.asarray()
        return data

    def calculate_normalized_variance(self, data):
        return np.var(data) / np.mean(data)
    

    def assign_plane(self, group, offset):
        idxmax = group['delta_normalized_variance'].idxmax() 
        offset_x = group.index.get_loc(idxmax) + offset
        
        planes = (np.arange(len(group)) - offset_x)
        planes = np.where(planes < 0, pd.NA, planes) # Replace negative plane values (i.e. rows before max) with NaN; take a maximum plane limit?
        
        group['Metadata_Plane'] = pd.Series(planes, index=group.index, dtype='Int64')
        self.results = group

   
    def postprocess(self, df, fmin):
        """
        Discard any wells that do not meet the minimum focus score.
        """
       
        #Identify the wells that meet the condition for plane 0
        wells_of_interest = df.loc[
            (df['Metadata_Plane'] == 0) & (df['normalized_variance'] > fmin),
                'Metadata_Well'].unique()

        filtered_df = df[df['Metadata_Well'].isin(wells_of_interest)]
        
        self.results = filtered_df
    
    def visualize(self):
        """
        Visualize detected spheres, works on the results of the detect_spheres method.
        #TODO: think about the most practical implementation
        """
        # df = self.results

        # df = df.sort_values(by='Metadata_Z')
        # df_grouped = df.groupby('Metadata_Well')

        # # Then plot the normalized variance across Z for each well
        # fig, ax = plt.subplots()
        # for name, group in df_grouped:
        #     ax.plot(group['Metadata_Z'], group['d_normalized_variance'], label=name)
        pass

    
    def run(
            self: object, 
            regex: str = r'([A-P]\d{1,2})Z(\d+)C03', #TODO: is this the best way to do this?
            channel: str = 'SYTO',
            image_path: str = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet', 
            z_info : str = 'Metadata_Plane',
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
            a path to the folder with images or a path to the cellprofiler output
        regex : str, default r'Z(\d+)C03'
            pattern that can collect metadata from the images. Only is CellProfiler data is not provided.
        channel : str, default 'SYTO'
            channel to perform detection on, needs to match the channelname in the cellprofiler output.
        cellprofiler_output : 
            path to cellprofiler output, should take both csv and parquet
        image_path : 
            directory of all your raw images. 
        z_info : str, default 'Metadata_Site'
            column name in the cellprofiler output that contains the Z/plsne/section information. 
            Neces
            If you are using raw images, this will be ignored.
        offset : int, default -2
            value to offset the starting plane. Subtracting 2 works well in our case.
        fmin : float, default 250
            minimum value for the focus score at the maximum change. In practice this will help weed out some non-spheroid images, or poor qualiy spheroids. 
            likely needs to be calibrated for each setup, and assay. 
        visualize : Boolean, default False
            True or False
        """

        self.load_data(image_path, regex, channel, flag)
        
        results = self.detect_spheres(offset, fmin) # TODO: Fix this
               
        if visualize: 
            self.visualize()

        # return results


# --------------------------------------------------------------------------------------------------------------------
# Example usage 
if __name__ == "__main__":
    detector = SphereDetect()
    detected_spheres = detector.run(
        regex="some_regex_pattern",
        channel="syto",
        image_path="/path/to/your/parquet/or/folder",
        flag="cellprofiler",  # or "raw_images"
        offset=-2,
        fmin=250,
        visualize=False
    )

    print(detected_spheres)

