package org.greendial.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * In-app APK update for sideloaded GreenDial builds.
 * JS: Capacitor.Plugins.AppUpdate.getVersion() / downloadAndInstall({ url })
 */
@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {

    @PluginMethod
    public void getVersion(PluginCall call) {
        try {
            PackageManager pm = getContext().getPackageManager();
            PackageInfo info = pm.getPackageInfo(getContext().getPackageName(), 0);
            JSObject ret = new JSObject();
            ret.put("versionName", info.versionName != null ? info.versionName : "0");
            long code;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                code = info.getLongVersionCode();
            } else {
                //noinspection deprecation
                code = info.versionCode;
            }
            ret.put("versionCode", code);
            ret.put("packageName", getContext().getPackageName());
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("Could not read app version: " + e.getMessage());
        }
    }

    @PluginMethod
    public void canInstallPackages(PluginCall call) {
        JSObject ret = new JSObject();
        boolean allowed = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            allowed = getContext().getPackageManager().canRequestPackageInstalls();
        }
        ret.put("allowed", allowed);
        call.resolve(ret);
    }

    @PluginMethod
    public void openInstallSettings(PluginCall call) {
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
            intent.setData(Uri.parse("package:" + getContext().getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            try {
                Intent intent = new Intent(Settings.ACTION_SECURITY_SETTINGS);
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(intent);
                call.resolve();
            } catch (Exception e2) {
                call.reject("Could not open install settings: " + e2.getMessage());
            }
        }
    }

    @PluginMethod
    public void downloadAndInstall(PluginCall call) {
        String url = call.getString("url");
        if (url == null || url.isEmpty()) {
            call.reject("url required");
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!getContext().getPackageManager().canRequestPackageInstalls()) {
                JSObject ret = new JSObject();
                ret.put("needsPermission", true);
                ret.put("message", "Allow GreenDial to install updates in system settings, then try again.");
                call.resolve(ret);
                return;
            }
        }

        // Hold the call across the background download
        bridge.saveCall(call);
        final String callbackId = call.getCallbackId();
        final String downloadUrl = url;

        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                File dir = new File(getContext().getCacheDir(), "updates");
                if (!dir.exists() && !dir.mkdirs()) {
                    rejectSaved(callbackId, "Could not create update folder");
                    return;
                }
                File apkFile = new File(dir, "GreenDial-update.apk");
                if (apkFile.exists()) {
                    //noinspection ResultOfMethodCallIgnored
                    apkFile.delete();
                }

                URL u = new URL(downloadUrl);
                conn = (HttpURLConnection) u.openConnection();
                conn.setConnectTimeout(30000);
                conn.setReadTimeout(180000);
                conn.setInstanceFollowRedirects(true);
                conn.connect();
                int code = conn.getResponseCode();
                // Follow one redirect manually if needed
                if (code == HttpURLConnection.HTTP_MOVED_TEMP
                        || code == HttpURLConnection.HTTP_MOVED_PERM
                        || code == HttpURLConnection.HTTP_SEE_OTHER
                        || code == 307 || code == 308) {
                    String loc = conn.getHeaderField("Location");
                    conn.disconnect();
                    conn = (HttpURLConnection) new URL(loc).openConnection();
                    conn.setConnectTimeout(30000);
                    conn.setReadTimeout(180000);
                    conn.connect();
                    code = conn.getResponseCode();
                }
                if (code < 200 || code >= 300) {
                    rejectSaved(callbackId, "Download failed (HTTP " + code + ")");
                    return;
                }

                try (InputStream in = conn.getInputStream();
                     FileOutputStream out = new FileOutputStream(apkFile)) {
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) >= 0) {
                        out.write(buf, 0, n);
                    }
                    out.flush();
                }

                if (apkFile.length() < 10000) {
                    rejectSaved(callbackId, "Downloaded file looks too small — try again");
                    return;
                }

                final File installFile = apkFile;
                Activity activity = getActivity();
                if (activity == null) {
                    rejectSaved(callbackId, "Activity unavailable");
                    return;
                }
                activity.runOnUiThread(() -> {
                    PluginCall saved = bridge.getSavedCall(callbackId);
                    if (saved == null) return;
                    try {
                        installApk(installFile);
                        JSObject ret = new JSObject();
                        ret.put("ok", true);
                        ret.put("startedInstall", true);
                        saved.resolve(ret);
                    } catch (Exception e) {
                        saved.reject("Install failed: " + e.getMessage());
                    } finally {
                        bridge.releaseCall(saved);
                    }
                });
            } catch (Exception e) {
                rejectSaved(callbackId, "Update failed: " + e.getMessage());
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private void rejectSaved(String callbackId, String msg) {
        Activity activity = getActivity();
        Runnable r = () -> {
            PluginCall saved = bridge.getSavedCall(callbackId);
            if (saved != null) {
                saved.reject(msg);
                bridge.releaseCall(saved);
            }
        };
        if (activity != null) {
            activity.runOnUiThread(r);
        } else {
            r.run();
        }
    }

    private void installApk(File apkFile) {
        Uri uri = FileProvider.getUriForFile(
                getContext(),
                getContext().getPackageName() + ".fileprovider",
                apkFile
        );
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(intent);
    }
}
