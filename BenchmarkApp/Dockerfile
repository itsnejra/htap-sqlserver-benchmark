FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Restore ovisnosti (layer cache)
COPY HTAPBenchmark.sln .
COPY HTAPBenchmark.Core/HTAPBenchmark.Core.csproj HTAPBenchmark.Core/
COPY HTAPBenchmark.Runner/HTAPBenchmark.Runner.csproj HTAPBenchmark.Runner/
RUN dotnet restore HTAPBenchmark.sln

# Build & publish
COPY HTAPBenchmark.Core/ HTAPBenchmark.Core/
COPY HTAPBenchmark.Runner/ HTAPBenchmark.Runner/
RUN dotnet publish HTAPBenchmark.Runner/HTAPBenchmark.Runner.csproj \
    -c Release \
    -o /app/publish \
    --no-restore

FROM mcr.microsoft.com/dotnet/runtime:8.0 AS runtime
WORKDIR /app

COPY --from=build /app/publish .

# Rezultati se pišu u /app/Results (mount point u docker-compose)
RUN mkdir -p /app/Results

ENTRYPOINT ["dotnet", "HTAPBenchmark.dll"]
