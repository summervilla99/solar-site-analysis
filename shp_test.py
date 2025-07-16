import geopandas as gpd

# SHP 파일 불러오기
gdf = gpd.read_file('data/충북_청주시_청원구/LSMD_CONT_LDREG_43114_202507.dbf')

# 컬럼 목록 확인
print(gdf.columns)

# 데이터 샘플 확인
print(gdf.head())

# 지목 컬럼 값 분포 확인
# print(gdf['지목'].value_counts())