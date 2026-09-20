name: Build APK

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install buildozer cython==0.29.36
          sudo apt-get update
          sudo apt-get install -y openjdk-11-jdk git
      
      - name: Build APK
        run: |
          buildozer android debug
      
      - name: Upload APK
        uses: actions/upload-artifact@v2
        with:
          name: apk
          path: bin/osttube-1.0-debug.apk
