from cx_Freeze import setup, Executable

setup(name = "Cylance" ,
      version = "0.1" ,
      description = "Does Cyalnce API calls to remove computers from the Cylance console" ,
      executables = [Executable("cylance.py")])