package ccfg

import (
	"archive/tar"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// GitHubRepo is where the releases live.
const GitHubRepo = "dreamyang-liu/claude-config"

// LatestVersion resolves the tag that /releases/latest redirects to.
func LatestVersion() (string, error) {
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Head("https://github.com/" + GitHubRepo + "/releases/latest")
	if err != nil {
		return "", err
	}
	resp.Body.Close()
	final := resp.Request.URL.Path
	tag := final[strings.LastIndex(final, "/")+1:]
	if !strings.HasPrefix(tag, "v") {
		return "", fmt.Errorf("no release found at https://github.com/%s/releases", GitHubRepo)
	}
	return tag, nil
}

// SelfUpdate replaces the running binary with the release `version` ("" for
// the latest). It verifies the sha256 from checksums.txt and writes the new
// file next to the old one before it renames it into place. It returns the
// installed version and whether anything changed.
func SelfUpdate(current, version string) (string, bool, error) {
	if version == "" {
		var err error
		version, err = LatestVersion()
		if err != nil {
			return "", false, err
		}
	}
	if version == current {
		return version, false, nil
	}
	exe, err := os.Executable()
	if err != nil {
		return "", false, err
	}
	real, err := filepath.EvalSymlinks(exe)
	if err != nil {
		return "", false, err
	}
	asset := fmt.Sprintf("ccfg_%s_%s_%s.tar.gz", version, runtime.GOOS, runtime.GOARCH)
	base := fmt.Sprintf("https://github.com/%s/releases/download/%s/", GitHubRepo, version)
	archive, err := download(base + asset)
	if err != nil {
		return "", false, err
	}
	sums, err := download(base + "checksums.txt")
	if err != nil {
		return "", false, err
	}
	if err := verify(archive, asset, sums); err != nil {
		return "", false, err
	}
	binary, err := extractBinary(archive)
	if err != nil {
		return "", false, err
	}
	tmp := real + ".new"
	if err := os.WriteFile(tmp, binary, 0o755); err != nil {
		return "", false, err
	}
	if err := os.Rename(tmp, real); err != nil {
		os.Remove(tmp)
		return "", false, err
	}
	return version, true, nil
}

func download(url string) ([]byte, error) {
	client := &http.Client{Timeout: 2 * time.Minute}
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download %s: HTTP %d", url, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func verify(archive []byte, asset string, sums []byte) error {
	sum := sha256.Sum256(archive)
	actual := hex.EncodeToString(sum[:])
	for _, line := range strings.Split(string(sums), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 2 && strings.TrimPrefix(fields[1], "./") == asset {
			if fields[0] != actual {
				return fmt.Errorf("checksum mismatch for %s", asset)
			}
			return nil
		}
	}
	return fmt.Errorf("no checksum for %s", asset)
}

func extractBinary(archive []byte) ([]byte, error) {
	gz, err := gzip.NewReader(strings.NewReader(string(archive)))
	if err != nil {
		return nil, err
	}
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if errors.Is(err, io.EOF) {
			return nil, errors.New("the archive holds no ccfg binary")
		}
		if err != nil {
			return nil, err
		}
		if filepath.Base(hdr.Name) == "ccfg" {
			return io.ReadAll(tr)
		}
	}
}
