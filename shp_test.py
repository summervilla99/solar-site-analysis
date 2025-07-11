import geopandas as gpd

# SHP 파일 불러오기
gdf = gpd.read_file('data/LSMD_CONT_LDREG_43130_202506.dbf')

# 컬럼 목록 확인
print(gdf.columns)

# 데이터 샘플 확인
print(gdf.head())

# 지목 컬럼 값 분포 확인
# print(gdf['지목'].value_counts())