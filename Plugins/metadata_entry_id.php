<?php
/*
Plugin Name: Brimming - Custom Metadata Entry ID
Description: Add entry ID's from contentful to metadata column for each page
Version: 1.0
Author: Emre Gumus
*/

add_filter( 'rest_enabled', '__return_true' );

// Add a meta box for the metadata ID
function add_metadata_id_meta_box() {
    $screens = ['page', 'post']; // Add 'post' to the screens array
    foreach ($screens as $screen) {
        add_meta_box(
            'metadata_id_meta_box', // ID
            'Metadata ID', // Title
            'metadata_id_meta_box_callback', // Callback
            $screen, // Screen (post type)
            'side', // Context
            'high' // Priority
        );
    }
}
add_action('add_meta_boxes', 'add_metadata_id_meta_box');

function metadata_id_meta_box_callback($post) {
    // Add a nonce field for security
    wp_nonce_field('save_metadata_id', 'metadata_id_nonce');

    // Get the current value of the metadata ID
    $metadata_id = get_post_meta($post->ID, '_metadata_id', true);

    echo '<label for="metadata_id">Metadata ID: </label>';
    echo '<input type="text" id="metadata_id" name="metadata_id" value="' . esc_attr($metadata_id) . '" />';
}

function save_metadata_id($post_id) {
    // Check if nonce is set
    if (!isset($_POST['metadata_id_nonce'])) {
        return $post_id;
    }

    // Verify the nonce
    if (!wp_verify_nonce($_POST['metadata_id_nonce'], 'save_metadata_id')) {
        return $post_id;
    }

    // Check if this is an autosave
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return $post_id;
    }

    // Check user permissions
    if (isset($_POST['post_type']) && in_array($_POST['post_type'], ['page', 'post'], true)) {
        if (!current_user_can('edit_post', $post_id)) {
            return $post_id;
        }
    } else {
        if (!current_user_can('edit_post', $post_id)) {
            return $post_id;
        }
    }

    // Sanitize the user input
    $metadata_id = sanitize_text_field($_POST['metadata_id']);

    // Update the metadata ID
    update_post_meta($post_id, '_metadata_id', $metadata_id);
}
add_action('save_post', 'save_metadata_id');

// Add custom columns to the pages and posts screens
function add_metadata_id_column($columns) {
    $columns['metadata_id'] = 'Metadata ID';
    return $columns;
}
add_filter('manage_page_posts_columns', 'add_metadata_id_column');
add_filter('manage_post_posts_columns', 'add_metadata_id_column'); // Added for posts

// Populate the custom columns with data
function metadata_id_column_content($column, $post_id) {
    if ($column === 'metadata_id') {
        $metadata_id = get_post_meta($post_id, '_metadata_id', true);
        echo esc_html($metadata_id);
    }
}
add_action('manage_page_posts_custom_column', 'metadata_id_column_content', 10, 2);
add_action('manage_post_posts_custom_column', 'metadata_id_column_content', 10, 2); // Added for posts

// Make the custom columns sortable
function metadata_id_column_sortable($columns) {
    $columns['metadata_id'] = 'metadata_id';
    return $columns;
}
add_filter('manage_edit-page_sortable_columns', 'metadata_id_column_sortable');
add_filter('manage_edit-post_sortable_columns', 'metadata_id_column_sortable'); // Added for posts

// Order the posts by metadata ID when sorting
function metadata_id_orderby($query) {
    if (!is_admin() || !$query->is_main_query()) {
        return;
    }

    if ('metadata_id' === $query->get('orderby')) {
        $query->set('meta_key', '_metadata_id');
        $query->set('orderby', 'meta_value');
    }
}
add_action('pre_get_posts', 'metadata_id_orderby');

// Register metadata for the REST API
function register_metadata_id_for_rest_api() {
    register_meta('post', '_metadata_id', [
        'show_in_rest' => true,
        'type' => 'string',
        'single' => true,
        'sanitize_callback' => 'sanitize_text_field',
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ]);
}
add_action('init', 'register_metadata_id_for_rest_api');