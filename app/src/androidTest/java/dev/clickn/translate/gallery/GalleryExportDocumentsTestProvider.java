package dev.clickn.translate.gallery;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import java.io.File;
import java.io.FileNotFoundException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Remote test APK process: framework/Java only; target Kotlin dependencies are not on its classpath. */
public final class GalleryExportDocumentsTestProvider extends DocumentsProvider {
    public static final String ROOT_ID = "owned-fixture-root";
    public static final String GRANT_METHOD = "owned-fixture-grant";
    public static final String REVOKE_METHOD = "owned-fixture-revoke";
    public static final String ACK_COMPLETED = "owned-fixture-completed";
    private static final String[] DOCUMENT_COLUMNS = {
        Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE,
        Document.COLUMN_SIZE, Document.COLUMN_FLAGS
    };

    private static final class OwnedDocument {
        final File file;
        final String mime;
        final String name;
        OwnedDocument(File file, String mime, String name) {
            this.file = file;
            this.mime = mime;
            this.name = name;
        }
    }

    private final Map<String, OwnedDocument> documents = new HashMap<>();
    private File ownedRoot;

    @Override public boolean onCreate() {
        if (getContext() == null) return false;
        ownedRoot = new File(getContext().getFilesDir(), "gallery-export-provider-" + UUID.randomUUID());
        return ownedRoot.mkdir();
    }

    @Override public synchronized String createDocument(String parentId, String mime, String displayName)
            throws FileNotFoundException {
        require(ROOT_ID.equals(parentId));
        require(ownedRoot.exists() || ownedRoot.mkdir());
        String id = UUID.randomUUID().toString();
        File file = new File(ownedRoot, id);
        try {
            require(file.createNewFile());
        } catch (java.io.IOException error) {
            throw new FileNotFoundException("Owned fixture could not create a document");
        }
        documents.put(id, new OwnedDocument(file, mime, displayName));
        return id;
    }

    @Override public synchronized ParcelFileDescriptor openDocument(String id, String mode, CancellationSignal signal)
            throws FileNotFoundException {
        if (signal != null) signal.throwIfCanceled();
        return ParcelFileDescriptor.open(owned(id).file, ParcelFileDescriptor.parseMode(mode));
    }

    @Override public synchronized void deleteDocument(String id) throws FileNotFoundException {
        require(owned(id).file.delete());
        documents.remove(id);
        if (documents.isEmpty()) require(ownedRoot.delete());
    }

    @Override public synchronized Cursor queryDocument(String id, String[] projection) throws FileNotFoundException {
        String[] columns = projection != null ? projection : DOCUMENT_COLUMNS;
        MatrixCursor cursor = new MatrixCursor(columns);
        addDocument(cursor, id, columns);
        return cursor;
    }

    @Override public synchronized Cursor queryChildDocuments(String parentId, String[] projection, String sortOrder)
            throws FileNotFoundException {
        require(ROOT_ID.equals(parentId));
        String[] columns = projection != null ? projection : DOCUMENT_COLUMNS;
        MatrixCursor cursor = new MatrixCursor(columns);
        for (String id : documents.keySet()) addDocument(cursor, id, columns);
        return cursor;
    }

    @Override public Cursor queryRoots(String[] projection) {
        String[] columns = projection != null ? projection : new String[] {
            Root.COLUMN_ROOT_ID, Root.COLUMN_DOCUMENT_ID, Root.COLUMN_TITLE, Root.COLUMN_FLAGS
        };
        MatrixCursor cursor = new MatrixCursor(columns);
        MatrixCursor.RowBuilder row = cursor.newRow();
        for (String column : columns) {
            Object value = null;
            if (Root.COLUMN_ROOT_ID.equals(column) || Root.COLUMN_DOCUMENT_ID.equals(column)) value = ROOT_ID;
            else if (Root.COLUMN_TITLE.equals(column)) value = "Owned export fixture";
            else if (Root.COLUMN_FLAGS.equals(column)) value = Root.FLAG_SUPPORTS_CREATE;
            row.add(value);
        }
        return cursor;
    }

    @Override public synchronized boolean isChildDocument(String parentId, String id) {
        return ROOT_ID.equals(parentId) && documents.containsKey(id);
    }

    private void addDocument(MatrixCursor cursor, String id, String[] columns) throws FileNotFoundException {
        OwnedDocument document = ROOT_ID.equals(id) ? null : owned(id);
        MatrixCursor.RowBuilder row = cursor.newRow();
        for (String column : columns) {
            Object value = null;
            if (Document.COLUMN_DOCUMENT_ID.equals(column)) value = id;
            else if (Document.COLUMN_DISPLAY_NAME.equals(column)) value = document == null ? "Owned export fixture" : document.name;
            else if (Document.COLUMN_MIME_TYPE.equals(column)) value = document == null ? Document.MIME_TYPE_DIR : document.mime;
            else if (Document.COLUMN_SIZE.equals(column)) value = document == null ? 0L : document.file.length();
            else if (Document.COLUMN_FLAGS.equals(column)) value = document == null ? Document.FLAG_DIR_SUPPORTS_CREATE
                : Document.FLAG_SUPPORTS_WRITE | Document.FLAG_SUPPORTS_DELETE;
            row.add(value);
        }
    }

    private OwnedDocument owned(String id) throws FileNotFoundException {
        OwnedDocument document = documents.get(id);
        if (document == null) throw new FileNotFoundException("Unknown owned fixture");
        return document;
    }

    private static void require(boolean condition) {
        if (!condition) throw new IllegalStateException("Owned fixture operation failed");
    }
}
