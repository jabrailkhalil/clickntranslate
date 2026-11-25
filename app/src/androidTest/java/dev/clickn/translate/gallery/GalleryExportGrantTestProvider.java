package dev.clickn.translate.gallery;

import android.content.ComponentName;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ProviderInfo;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;
import android.provider.DocumentsContract;

/** Remote bootstrap controller: only a signed caller and one constant synthetic fixture tree. */
public final class GalleryExportGrantTestProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }

    @Override public Bundle call(String method, String client, Bundle extras) {
        boolean grant = GalleryExportDocumentsTestProvider.GRANT_METHOD.equals(method);
        if (!grant && !GalleryExportDocumentsTestProvider.REVOKE_METHOD.equals(method)) {
            return super.call(method, client, extras);
        }
        Context owner = getContext();
        if (owner == null || client == null || !client.equals(getCallingPackage()) ||
                owner.getPackageManager().checkSignatures(Binder.getCallingUid(), Process.myUid()) != PackageManager.SIGNATURE_MATCH) {
            throw new SecurityException("Untrusted owned fixture caller");
        }
        // Authenticate first, then perform the fixed grant as the provider owner.
        long identity = Binder.clearCallingIdentity();
        try {
            ProviderInfo documents = owner.getPackageManager().getProviderInfo(
                new ComponentName(owner, GalleryExportDocumentsTestProvider.class), 0);
            Uri tree = DocumentsContract.buildTreeDocumentUri(documents.authority, GalleryExportDocumentsTestProvider.ROOT_ID);
            int flags = Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION;
            if (grant) owner.grantUriPermission(client, tree, flags | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
            else owner.revokeUriPermission(client, tree, flags);
            Bundle acknowledgement = new Bundle();
            acknowledgement.putBoolean(GalleryExportDocumentsTestProvider.ACK_COMPLETED, true);
            return acknowledgement;
        } catch (PackageManager.NameNotFoundException error) {
            throw new IllegalStateException("Owned fixture provider unavailable");
        } finally {
            Binder.restoreCallingIdentity(identity);
        }
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) { return null; }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException("No fixture control documents"); }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) { throw new UnsupportedOperationException("No fixture control documents"); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) { throw new UnsupportedOperationException("No fixture control documents"); }
}
