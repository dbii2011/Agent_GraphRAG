data = [(3, 'Alice'), (25, 'Bob'), (35, 'Charlie')]
df = spark.createDataFrame(data, ['Age', 'Name'])
df.show()